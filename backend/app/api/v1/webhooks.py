"""
Webhook endpoints for external callbacks:
- /webhook/lex — Lex V2 fulfillment Lambda (donor chat responses)
- /webhook/sfn-callback — Step Functions task token callbacks
- /webhook/donor-response — Direct donor response link (email/SMS click)
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import boto3
from boto3.dynamodb.conditions import Attr
from app.config import get_settings
from app.services.communicator import record_donor_response
from app.services.feedback_loop import update_donor_after_outcome, log_failure_pattern

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("bloodbridge.webhooks")


class LexFulfillmentEvent(BaseModel):
    sessionId: str
    inputTranscript: str
    interpretations: Optional[list] = None
    sessionState: Optional[dict] = None


class SfnCallbackPayload(BaseModel):
    task_token: str
    outcome: str  # "confirmed" | "declined" | "rescheduled" | "no_response"
    donor_id: str
    request_id: str


class DonorResponsePayload(BaseModel):
    donor_id: str
    request_id: str
    notification_id: str
    response: str  # "confirmed" | "declined" | "rescheduled"


class DonorVolunteerPayload(BaseModel):
    donor_id: str
    request_id: str
    blood_group: str


@router.post("/donor-volunteer")
def donor_volunteer(data: DonorVolunteerPayload):
    """
    A donor volunteers directly for an open request.
    1. Records a confirmed notification entry.
    2. Adds a blood unit to inventory (status=Collected) for this donor's blood group.
    3. Reserves that unit for this request.
    4. Updates request status to 'matched'.
    """
    import uuid
    from datetime import datetime, date, timedelta

    now = datetime.utcnow().isoformat()
    notification_id = str(uuid.uuid4())

    dyn = boto3.resource("dynamodb", region_name=settings.AWS_REGION)

    # Log a notification record
    dyn.Table(settings.DYNAMODB_NOTIFICATIONS_TABLE).put_item(Item={
        "notification_id": notification_id,
        "donor_id": data.donor_id,
        "request_id": data.request_id,
        "channel": "volunteer",
        "status": "responded",
        "response": "confirmed",
        "urgency": "standard",
        "sent_at": now,
        "response_timestamp": now,
        "message_preview": f"Donor volunteered for {data.blood_group} request",
    })

    # Add a blood unit to inventory for this donation commitment
    blood_unit_id = str(uuid.uuid4())
    coll_date = date.today()
    inv_table = dyn.Table(settings.DYNAMODB_INVENTORY_TABLE)
    try:
        inv_table.put_item(Item={
            "blood_unit_id": blood_unit_id,
            "blood_group": data.blood_group,
            "donor_id": data.donor_id,
            "collection_date": str(coll_date),
            "expiry_date": str(coll_date + timedelta(days=35)),
            "status": "Reserved",                     # reserved immediately for this request
            "reserved_for_request": data.request_id,
            "created_at": now,
        })
        logger.info(f"Created inventory unit {blood_unit_id} for volunteer donor {data.donor_id}")
    except Exception as e:
        logger.error(f"Could not create inventory unit for volunteer: {e}")
        blood_unit_id = None

    # Update donor stats
    try:
        update_donor_after_outcome(data.donor_id, "donated", data.request_id)
    except Exception as e:
        logger.warning(f"Could not update donor stats: {e}")

    # Update request to matched with volunteer info
    req_table = dyn.Table(settings.DYNAMODB_REQUESTS_TABLE)
    try:
        update_expr = "SET #s = :matched, volunteer_donor_id = :did, updated_at = :now"
        expr_values = {":matched": "matched", ":did": data.donor_id, ":now": now}
        if blood_unit_id:
            update_expr += ", volunteer_blood_unit_id = :uid"
            expr_values[":uid"] = blood_unit_id
        req_table.update_item(
            Key={"request_id": data.request_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues=expr_values,
        )
    except Exception as e:
        logger.error(f"Could not update request after volunteer: {e}")

    logger.info(f"Donor {data.donor_id} volunteered for request {data.request_id}")
    return {
        "status": "confirmed",
        "notification_id": notification_id,
        "blood_unit_id": blood_unit_id,
        "message": "Thank you! Your donation has been recorded. The blood bank will contact you shortly.",
    }


@router.get("/donor-notifications")
def get_donor_notifications(donor_id: str):
    """
    Fetch all notifications sent to a specific donor.
    Used by the Donor Portal to show pending donation requests.
    """
    table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_NOTIFICATIONS_TABLE
    )
    resp = table.scan(FilterExpression=Attr("donor_id").eq(donor_id))
    items = resp.get("Items", [])
    items.sort(key=lambda x: x.get("sent_at", ""), reverse=True)
    return {"notifications": items, "count": len(items)}


@router.post("/donor-response")
def handle_donor_response(data: DonorResponsePayload):
    """
    Called when a donor confirms/declines a notification.
    Records the response, updates the request status, and triggers the feedback loop.
    """
    valid_responses = {"confirmed", "declined", "rescheduled"}
    if data.response not in valid_responses:
        raise HTTPException(status_code=400, detail=f"Invalid response. Must be one of: {valid_responses}")

    record_donor_response(data.notification_id, data.donor_id, data.response)

    now = datetime.utcnow().isoformat()
    req_table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_REQUESTS_TABLE
    )

    if data.response == "confirmed":
        # Donor confirmed → move request to matched
        try:
            req_table.update_item(
                Key={"request_id": data.request_id},
                UpdateExpression="SET #s = :matched, confirmed_donor_id = :did, updated_at = :now",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":matched": "matched",
                    ":did": data.donor_id,
                    ":now": now,
                },
            )
        except Exception as e:
            logger.warning(f"Could not update request status to matched: {e}")
        update_donor_after_outcome(
            donor_id=data.donor_id,
            outcome="donated",
            request_id=data.request_id,
        )
    elif data.response == "declined":
        update_donor_after_outcome(
            donor_id=data.donor_id,
            outcome="declined",
            request_id=data.request_id,
        )

    logger.info(f"Donor {data.donor_id} responded '{data.response}' to request {data.request_id}")
    return {"status": "recorded", "response": data.response}


@router.post("/lex-fulfillment")
async def lex_fulfillment(request: Request):
    """
    Lex V2 fulfillment Lambda endpoint.
    Processes DonorResponseBot intents and records session state.
    """
    body = await request.json()
    session_state = body.get("sessionState", {})
    intent = session_state.get("intent", {})
    intent_name = intent.get("name", "")
    slots = intent.get("slots", {})
    session_attrs = session_state.get("sessionAttributes", {})

    donor_id = session_attrs.get("donor_id", "")
    request_id = session_attrs.get("request_id", "")

    response_message = ""
    fulfillment_state = "Fulfilled"

    if intent_name == "ConfirmDonation":
        response_message = (
            "Thank you! Your donation is confirmed. You'll receive the blood bank address and timing shortly. "
            "Reply 'CANCEL' if plans change. You're saving a life!"
        )
        if donor_id and request_id:
            record_donor_response(session_attrs.get("notification_id", ""), donor_id, "confirmed")
            update_donor_after_outcome(donor_id, "donated", request_id)

    elif intent_name == "RescheduleDonation":
        new_date = (slots.get("NewDate") or {}).get("value", {}).get("interpretedValue", "")
        response_message = (
            f"Noted! We've updated your donation for {new_date}. "
            "The blood bank will confirm your new slot via SMS. Thank you for letting us know!"
        )
        if donor_id and request_id:
            record_donor_response(session_attrs.get("notification_id", ""), donor_id, "rescheduled")

    elif intent_name == "DeclineDonation":
        response_message = (
            "Understood, no worries. We'll reach out next time when you're eligible. "
            "Stay healthy and thank you for being a registered donor!"
        )
        if donor_id and request_id:
            record_donor_response(session_attrs.get("notification_id", ""), donor_id, "declined")
            update_donor_after_outcome(donor_id, "declined", request_id)

    elif intent_name == "AskQuestion":
        question = body.get("inputTranscript", "")
        response_message = (
            "For any questions about the donation process, blood bank locations, or eligibility, "
            "please call our helpline at 1800-XXX-XXXX or visit bloodbridge.ai/faq. "
            "Our team is available 8 AM – 8 PM."
        )
    else:
        response_message = (
            "I didn't quite understand that. You can say: "
            "'YES' to confirm donation, 'RESCHEDULE' to pick another date, or 'NO' to decline."
        )
        fulfillment_state = "Failed"

    # Persist session to DynamoDB
    if donor_id:
        _save_lex_session(donor_id, intent_name, body.get("inputTranscript", ""), response_message, session_attrs)

    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent_name, "state": fulfillment_state},
            "sessionAttributes": session_attrs,
        },
        "messages": [{"contentType": "PlainText", "content": response_message}],
    }


def _save_lex_session(donor_id: str, intent: str, user_text: str, bot_text: str, session_attrs: dict):
    """Persist last 5 conversation turns to bb_sessions for memory."""
    import boto3, uuid
    sessions = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_SESSIONS_TABLE
    )
    now = datetime.utcnow().isoformat()
    new_turns = [
        {"speaker": "user", "text": user_text, "timestamp": now},
        {"speaker": "bot", "text": bot_text, "timestamp": now},
    ]
    try:
        existing = sessions.get_item(Key={"donor_id": donor_id, "session_id": "latest"}).get("Item", {})
        history = existing.get("conversation_history", [])
        history = (history + new_turns)[-10:]  # Keep last 10 turns (5 exchanges)
        sessions.put_item(Item={
            "donor_id": donor_id,
            "session_id": "latest",
            "last_intent": intent,
            "lex_session_attributes": session_attrs,
            "conversation_history": history,
            "updated_at": now,
        })
    except Exception as e:
        logger.error(f"Failed to save Lex session: {e}")


class ChatMessage(BaseModel):
    message: str
    donor_id: str = ""
    request_id: str = ""
    notification_id: str = ""
    session_id: str = "default-session"


@router.post("/chat")
def chat_with_lex(data: ChatMessage):
    """
    Frontend chat proxy: sends a message to Lex Runtime and returns the bot reply.
    Falls back to local intent matching if Lex is not configured.
    """
    import boto3
    import re

    bot_id = settings.LEX_BOT_ID
    alias_id = settings.LEX_BOT_ALIAS_ID

    # Try real Lex Runtime if configured
    if bot_id and alias_id:
        try:
            lex_rt = boto3.client("lexv2-runtime", region_name=settings.AWS_REGION)
            resp = lex_rt.recognize_text(
                botId=bot_id,
                botAliasId=alias_id,
                localeId="en_IN",
                sessionId=data.session_id or data.donor_id or "anon",
                text=data.message,
                sessionState={
                    "sessionAttributes": {
                        "donor_id": data.donor_id,
                        "request_id": data.request_id,
                        "notification_id": data.notification_id,
                    }
                },
            )
            messages = resp.get("messages", [])
            reply = messages[0]["content"] if messages else "I didn't understand that. Try: YES, RESCHEDULE, or NO."
            return {"reply": reply, "source": "lex"}
        except Exception as e:
            logger.warning(f"Lex Runtime failed, using local fallback: {e}")

    # Local intent fallback
    text = data.message.lower().strip()
    if re.search(r"\byes\b|confirm|i will|count me|available|sure\b", text):
        reply = ("Thank you! Your donation is confirmed. You'll receive the blood bank address shortly. "
                 "Reply 'CANCEL' if plans change. You're saving a life!")
        if data.donor_id and data.request_id:
            try:
                record_donor_response(data.notification_id, data.donor_id, "confirmed")
                update_donor_after_outcome(data.donor_id, "donated", data.request_id)
            except Exception:
                pass
    elif re.search(r"\bno\b|decline|cannot|can't|not available", text):
        reply = ("Understood. We'll reach out next time. Stay healthy and thank you for being a registered donor!")
        if data.donor_id and data.request_id:
            try:
                record_donor_response(data.notification_id, data.donor_id, "declined")
                update_donor_after_outcome(data.donor_id, "declined", data.request_id)
            except Exception:
                pass
    elif re.search(r"reschedule|different date|change|another day", text):
        reply = ("Sure! Please share your preferred date and we'll update your slot. The blood bank will confirm via SMS.")
        if data.donor_id:
            try:
                record_donor_response(data.notification_id, data.donor_id, "rescheduled")
            except Exception:
                pass
    elif re.search(r"help|where|eligible|faq|how", text):
        reply = ("For questions about donation, call our helpline 1800-XXX-XXXX or visit bloodbridge.ai/faq. "
                 "Available 8 AM – 8 PM.")
    else:
        reply = ("I didn't quite catch that. You can say: 'YES' to confirm, 'RESCHEDULE' to pick another date, or 'NO' to decline.")

    return {"reply": reply, "source": "local"}


@router.post("/sfn-callback")
def sfn_task_callback(data: SfnCallbackPayload):
    """
    Called by Step Functions task token pattern when a manual approval is required.
    Sends success/failure signal back to Step Functions.
    """
    import boto3
    sf = boto3.client("stepfunctions", region_name=settings.AWS_REGION)

    try:
        if data.outcome in ("confirmed", "donated"):
            sf.send_task_success(
                taskToken=data.task_token,
                output='{"donor_confirmed": true}',
            )
        else:
            sf.send_task_success(
                taskToken=data.task_token,
                output='{"donor_confirmed": false}',
            )
        return {"status": "signaled", "outcome": data.outcome}
    except Exception as e:
        logger.error(f"SFN callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
