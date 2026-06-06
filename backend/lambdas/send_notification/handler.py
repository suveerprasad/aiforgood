"""
Lambda: bb-send-notification
Step Functions task — sends notification to the current ranked donor.
Generates personalised message using Bedrock before sending.
"""
import sys
import os
import boto3

sys.path.insert(0, "/var/task")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.services.communicator import send_donor_notification
from app.services.ai_insights import generate_donor_outreach_message
from app.config import get_settings

settings = get_settings()


def _get_donor(donor_id: str) -> dict:
    table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_USERS_TABLE
    )
    return table.get_item(Key={"user_id": donor_id}).get("Item", {})


def _get_session_history(donor_id: str) -> list:
    try:
        table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
            settings.DYNAMODB_SESSIONS_TABLE
        )
        item = table.get_item(Key={"donor_id": donor_id, "session_id": "latest"}).get("Item", {})
        return item.get("conversation_history", [])
    except Exception:
        return []


def handler(event, context):
    """
    Input: { request_id, blood_group, urgency_level, collection_date,
             ranked_donors: [...], current_donor_index: N }
    Output: { notification_id, donor_id, sent: bool }
    """
    request_id = event.get("request_id", "")
    blood_group = event.get("blood_group", "")
    urgency = event.get("urgency_level", "standard")
    collection_date = event.get("collection_date", "")
    ranked_donors = event.get("ranked_donors", [])
    donor_index = int(event.get("current_donor_index", 0))

    if donor_index >= len(ranked_donors):
        return {"sent": False, "reason": "no_more_donors", "request_id": request_id}

    donor_id = ranked_donors[donor_index]
    donor = _get_donor(donor_id)

    if not donor:
        return {"sent": False, "reason": "donor_not_found", "donor_id": donor_id}

    donor_name = donor.get("name") or donor_id[:8]
    session_history = _get_session_history(donor_id)

    message = generate_donor_outreach_message(
        donor_name=donor_name,
        patient_city="your city",
        blood_group=blood_group,
        collection_date=collection_date,
        session_history=session_history,
    )

    result = send_donor_notification(
        donor_id=donor_id,
        request_id=request_id,
        message=message,
        urgency=urgency,
    )

    return {
        "sent": result.get("success", False),
        "notification_id": result.get("notification_id"),
        "donor_id": donor_id,
        "channel": result.get("channel"),
        "request_id": request_id,
    }
