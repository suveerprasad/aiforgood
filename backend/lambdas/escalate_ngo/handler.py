"""
Lambda: bb-escalate-ngo
Final escalation step when no individual donors respond within the wait window.
Notifies the NGO/blood bank directly and marks the request as escalated.

Input:
  request_id, blood_group, units_needed, urgency_level, collection_date

Output:
  escalated (bool), escalation_channels (list)
"""
import sys
import os
import uuid
import logging
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
REQUESTS_TABLE = os.environ.get("DYNAMODB_REQUESTS_TABLE", "bb_requests")
NOTIFICATIONS_TABLE = os.environ.get("DYNAMODB_NOTIFICATIONS_TABLE", "bb_notifications")
SES_SENDER = os.environ.get("SES_SENDER_EMAIL", "noreply@bloodbridge.ai")
NGO_ALERT_EMAIL = os.environ.get("NGO_ALERT_EMAIL", SES_SENDER)
NGO_ALERT_PHONE = os.environ.get("NGO_ALERT_PHONE", "")


def handler(event, context):
    request_id = event.get("request_id", "")
    blood_group = event.get("blood_group", "")
    units_needed = event.get("units_needed", 1)
    urgency_level = event.get("urgency_level", "standard")
    collection_date = event.get("collection_date", "")

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    now = datetime.utcnow().isoformat()
    escalation_channels = []

    escalation_message = (
        f"URGENT NGO ESCALATION — BloodBridge AI\n\n"
        f"No donor has responded for the following critical request:\n\n"
        f"  Request ID:      {request_id[:8]}\n"
        f"  Blood Group:     {blood_group}\n"
        f"  Units Needed:    {units_needed}\n"
        f"  Urgency:         {urgency_level.upper()}\n"
        f"  Collection Date: {collection_date}\n\n"
        f"Immediate action required. Please activate the NGO emergency donor network.\n"
        f"Contact the nearest blood bank or registered volunteer groups.\n\n"
        f"— BloodBridge AI Escalation System\n{now}"
    )

    # Try SES alert to NGO
    if NGO_ALERT_EMAIL:
        try:
            ses = boto3.client("ses", region_name=REGION)
            ses.send_email(
                Source=SES_SENDER,
                Destination={"ToAddresses": [NGO_ALERT_EMAIL]},
                Message={
                    "Subject": {"Data": f"[ESCALATION] {blood_group} blood needed urgently — BloodBridge"},
                    "Body": {"Text": {"Data": escalation_message}},
                },
            )
            escalation_channels.append("email")
            logger.info(f"NGO escalation email sent for request {request_id}")
        except Exception as e:
            logger.error(f"NGO email escalation failed: {e}")

    # Try SNS alert
    if NGO_ALERT_PHONE:
        try:
            sns = boto3.client("sns", region_name=REGION)
            sms = (f"BloodBridge ESCALATION: {blood_group} x{units_needed} needed urgently "
                   f"by {collection_date}. Request: {request_id[:8]}. Activate NGO network NOW.")
            sns.publish(PhoneNumber=NGO_ALERT_PHONE, Message=sms)
            escalation_channels.append("sms")
        except Exception as e:
            logger.error(f"NGO SMS escalation failed: {e}")

    # Update request status to escalated
    try:
        dynamodb.Table(REQUESTS_TABLE).update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s = :esc, escalated_at = :now, escalation_level = :ngo",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":esc": "escalated",
                ":now": now,
                ":ngo": "ngo",
            },
        )
    except Exception as e:
        logger.error(f"Failed to update request status to escalated: {e}")

    # Log notification record
    notif_id = str(uuid.uuid4())
    try:
        dynamodb.Table(NOTIFICATIONS_TABLE).put_item(Item={
            "notification_id": notif_id,
            "donor_id": "NGO",
            "request_id": request_id,
            "channel": ",".join(escalation_channels) or "system",
            "status": "escalated",
            "urgency": urgency_level,
            "sent_at": now,
            "message_preview": escalation_message[:120],
        })
    except Exception as e:
        logger.error(f"Failed to log escalation notification: {e}")

    logger.info(f"NGO escalation complete for {request_id}: channels={escalation_channels}")
    return {
        **event,
        "escalated": len(escalation_channels) > 0,
        "escalation_channels": escalation_channels,
        "notification_id": notif_id,
        "new_status": "escalated",
    }
