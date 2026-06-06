"""
Lambda: bb-lex-fulfillment
Lex V2 fulfillment hook for the DonorResponseBot.
Handles 4 intents: ConfirmDonation, RescheduleDonation, DeclineDonation, AskQuestion.
"""
import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, "/var/task")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

import boto3
from app.services.communicator import record_donor_response
from app.services.feedback_loop import update_donor_after_outcome
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Standard Lex V2 fulfillment event handler."""
    session_state = event.get("sessionState", {})
    intent = session_state.get("intent", {})
    intent_name = intent.get("name", "")
    slots = intent.get("slots", {})
    session_attrs = session_state.get("sessionAttributes", {})

    donor_id = session_attrs.get("donor_id", "")
    request_id = session_attrs.get("request_id", "")
    notification_id = session_attrs.get("notification_id", "")

    logger.info(f"Lex intent: {intent_name}, donor: {donor_id}, request: {request_id}")

    if intent_name == "ConfirmDonation":
        message = (
            f"Thank you for confirming! We've noted your donation. "
            f"You'll receive blood bank details shortly. You're a life-saver!"
        )
        if donor_id and request_id:
            record_donor_response(notification_id, donor_id, "confirmed")
            update_donor_after_outcome(donor_id, "donated", request_id)
        fulfillment_state = "Fulfilled"

    elif intent_name == "RescheduleDonation":
        new_date_slot = slots.get("NewDate") or {}
        new_date = (new_date_slot.get("value") or {}).get("interpretedValue", "a new date")
        message = (
            f"We've updated your donation to {new_date}. "
            f"Our team will confirm the new slot with you. Thank you for staying committed!"
        )
        if donor_id and request_id:
            record_donor_response(notification_id, donor_id, "rescheduled")
        fulfillment_state = "Fulfilled"

    elif intent_name == "DeclineDonation":
        message = (
            "We understand. No worries at all! "
            "We'll reach out when you're eligible again. Stay healthy, and thank you for being registered!"
        )
        if donor_id and request_id:
            record_donor_response(notification_id, donor_id, "declined")
            update_donor_after_outcome(donor_id, "declined", request_id)
        fulfillment_state = "Fulfilled"

    elif intent_name == "AskQuestion":
        message = (
            "Great question! For donation process info, blood bank locations, or eligibility queries: "
            "📞 1800-XXX-XXXX (8 AM–8 PM) | 🌐 bloodbridge.ai/faq"
        )
        fulfillment_state = "Fulfilled"

    else:
        message = (
            "Sorry, I didn't catch that. You can say:\n"
            "• 'YES' or 'Confirm' — to confirm your donation\n"
            "• 'Reschedule' — to pick another date\n"
            "• 'No' or 'Decline' — to opt out\n"
            "• 'Help' — for FAQs"
        )
        fulfillment_state = "Failed"

    _save_session(donor_id, intent_name, event.get("inputTranscript", ""), message, session_attrs)

    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent_name, "state": fulfillment_state},
            "sessionAttributes": session_attrs,
        },
        "messages": [{"contentType": "PlainText", "content": message}],
    }


def _save_session(donor_id: str, intent: str, user_text: str, bot_text: str, session_attrs: dict):
    if not donor_id:
        return
    try:
        table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
            settings.DYNAMODB_SESSIONS_TABLE
        )
        now = datetime.utcnow().isoformat()
        existing = table.get_item(Key={"donor_id": donor_id, "session_id": "latest"}).get("Item", {})
        history = existing.get("conversation_history", [])
        history = (history + [
            {"speaker": "user", "text": user_text, "timestamp": now},
            {"speaker": "bot", "text": bot_text, "timestamp": now},
        ])[-10:]
        table.put_item(Item={
            "donor_id": donor_id,
            "session_id": "latest",
            "last_intent": intent,
            "lex_session_attributes": session_attrs,
            "conversation_history": history,
            "updated_at": now,
        })
    except Exception as e:
        logger.error(f"Session save error: {e}")
