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


@router.post("/donor-response")
def handle_donor_response(data: DonorResponsePayload):
    """
    Called when a donor clicks a response link in their notification.
    Records the response and triggers the feedback loop.
    """
    valid_responses = {"confirmed", "declined", "rescheduled"}
    if data.response not in valid_responses:
        raise HTTPException(status_code=400, detail=f"Invalid response. Must be one of: {valid_responses}")

    record_donor_response(data.notification_id, data.donor_id, data.response)

    if data.response in ("confirmed", "declined"):
        update_donor_after_outcome(
            donor_id=data.donor_id,
            outcome="donated" if data.response == "confirmed" else "declined",
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
