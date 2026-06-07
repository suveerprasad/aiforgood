"""
Lambda: bb-schedule-donation
Sends a confirmed donor their donation appointment details via SES/SNS.
Called by Step Functions after a donor confirms via chat or link.

Input:
  donor_id, request_id, collection_date, blood_group, urgency_level

Output:
  scheduled (bool), notification_id
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
USERS_TABLE = os.environ.get("DYNAMODB_USERS_TABLE", "bb_users")
NOTIFICATIONS_TABLE = os.environ.get("DYNAMODB_NOTIFICATIONS_TABLE", "bb_notifications")
SES_SENDER = os.environ.get("SES_SENDER_EMAIL", "noreply@bloodbridge.ai")


def _get_donor(donor_id: str) -> dict:
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    resp = dynamodb.Table(USERS_TABLE).get_item(Key={"user_id": donor_id})
    return resp.get("Item", {})


def _log_notification(notification_id, donor_id, request_id, channel, status, message):
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    try:
        dynamodb.Table(NOTIFICATIONS_TABLE).put_item(Item={
            "notification_id": notification_id,
            "donor_id": donor_id,
            "request_id": request_id,
            "channel": channel,
            "status": status,
            "urgency": "standard",
            "sent_at": datetime.utcnow().isoformat(),
            "message_preview": message[:120],
        })
    except Exception as e:
        logger.error(f"Failed to log notification: {e}")


def handler(event, context):
    donor_id = event.get("donor_id", "")
    request_id = event.get("request_id", "")
    collection_date = event.get("collection_date", "")
    blood_group = event.get("blood_group", "")
    notification_id = str(uuid.uuid4())

    donor = _get_donor(donor_id)
    if not donor:
        logger.error(f"Donor not found: {donor_id}")
        return {**event, "scheduled": False, "notification_id": notification_id}

    appointment_message = (
        f"Dear {donor.get('name', 'Donor')},\n\n"
        f"Your blood donation appointment is confirmed!\n\n"
        f"Details:\n"
        f"  Blood Group: {blood_group}\n"
        f"  Collection Date: {collection_date}\n"
        f"  Location: Hyderabad Central Blood Bank, Road No. 12, Banjara Hills\n"
        f"  Time: 9:00 AM – 5:00 PM (walk-in)\n\n"
        f"Request Reference: {request_id[:8]}\n\n"
        f"Please bring a valid photo ID. Stay hydrated before donating.\n"
        f"Thank you for saving a life!\n\n"
        f"— BloodBridge AI Team"
    )

    ses = boto3.client("ses", region_name=REGION)
    email = donor.get("email") or donor.get("phone_number", "")
    sent = False

    if email and "@" in email:
        try:
            ses.send_email(
                Source=SES_SENDER,
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": "Your Blood Donation Appointment — BloodBridge AI"},
                    "Body": {"Text": {"Data": appointment_message}},
                },
            )
            sent = True
            channel = "email"
        except Exception as e:
            logger.error(f"SES failed for {donor_id}: {e}")
            channel = "email"
    else:
        phone = donor.get("phone_number", "")
        channel = "sms"
        if phone:
            try:
                sns = boto3.client("sns", region_name=REGION)
                sms_msg = (
                    f"BloodBridge: Donation confirmed for {blood_group} on {collection_date}. "
                    f"Visit Hyderabad Central Blood Bank. Thank you!"
                )
                sns.publish(PhoneNumber=phone, Message=sms_msg)
                sent = True
            except Exception as e:
                logger.error(f"SNS failed for {donor_id}: {e}")

    _log_notification(notification_id, donor_id, request_id, channel,
                      "sent" if sent else "failed", appointment_message)

    logger.info(f"Donation scheduled for donor {donor_id}, sent={sent}")
    return {**event, "scheduled": sent, "notification_id": notification_id}
