"""
Communication orchestrator.

Sends consent-gated donor notifications via SES (email) or SNS (SMS).
Logs every outreach attempt to bb_notifications table.
"""
import uuid
import logging
from datetime import datetime
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Attr

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("bloodbridge.communicator")


def _ses():
    return boto3.client("ses", region_name=settings.AWS_REGION)


def _sns():
    return boto3.client("sns", region_name=settings.AWS_REGION)


def _notif_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_NOTIFICATIONS_TABLE
    )


def _users_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_USERS_TABLE
    )


def _get_donor_contact(donor_id: str) -> dict:
    resp = _users_table().get_item(Key={"user_id": donor_id})
    return resp.get("Item", {})


def send_email(to_address: str, subject: str, body_text: str, body_html: Optional[str] = None) -> bool:
    """Send a transactional email via Amazon SES."""
    try:
        msg = {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
        }
        if body_html:
            msg["Body"]["Html"] = {"Data": body_html, "Charset": "UTF-8"}
        _ses().send_email(
            Source=settings.SES_SENDER_EMAIL,
            Destination={"ToAddresses": [to_address]},
            Message=msg,
        )
        return True
    except Exception as e:
        logger.error(f"SES send failed to {to_address}: {e}")
        return False


def send_sms(phone_number: str, message: str) -> bool:
    """Send a transactional SMS via Amazon SNS."""
    try:
        _sns().publish(
            PhoneNumber=phone_number,
            Message=message,
            MessageAttributes={
                "AWS.SNS.SMS.SenderID": {"DataType": "String", "StringValue": settings.SNS_SMS_SENDER_ID},
                "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"},
            },
        )
        return True
    except Exception as e:
        logger.error(f"SNS send failed to {phone_number}: {e}")
        return False


def send_donor_notification(
    donor_id: str,
    request_id: str,
    message: str,
    urgency: str = "standard",
) -> dict:
    """
    Send notification to a donor.
    - For 'critical' urgency, SMS is forced.
    - Checks consent_given before sending.
    - Logs every attempt to bb_notifications.
    """
    donor = _get_donor_contact(donor_id)
    notification_id = str(uuid.uuid4())

    if not donor:
        return {"success": False, "reason": "donor_not_found", "notification_id": notification_id}

    if not donor.get("consent_given", True):
        _log_notification(notification_id, donor_id, request_id, "system", "failed",
                          "consent_declined", urgency)
        return {"success": False, "reason": "consent_declined", "notification_id": notification_id}

    channel = "sms" if urgency == "critical" else "email"
    success = False

    if channel == "sms":
        phone = donor.get("phone_number")
        if phone:
            success = send_sms(phone, message)
        else:
            # Fallback to email when no phone
            email = donor.get("email")
            channel = "email"
            if email:
                success = send_email(email, "BloodBridge — Urgent Blood Donation Request", message)
    else:
        email = donor.get("email")
        if email:
            success = send_email(email, "BloodBridge — Blood Donation Request", message)

    _log_notification(notification_id, donor_id, request_id, channel,
                      "sent" if success else "failed", None, urgency, message[:120])
    return {"success": success, "notification_id": notification_id, "channel": channel}


def _log_notification(
    notification_id: str,
    donor_id: str,
    request_id: str,
    channel: str,
    status: str,
    response: Optional[str],
    urgency: str,
    message_preview: str = "",
):
    try:
        _notif_table().put_item(Item={
            "notification_id": notification_id,
            "donor_id": donor_id,
            "request_id": request_id,
            "channel": channel,
            "status": status,
            "response": response or "",
            "urgency": urgency,
            "sent_at": datetime.utcnow().isoformat(),
            "message_preview": message_preview,
        })
    except Exception as e:
        logger.error(f"Failed to log notification: {e}")


def record_donor_response(notification_id: str, donor_id: str, response: str) -> bool:
    """Record a donor's response (confirmed/declined/rescheduled) to a notification."""
    try:
        _notif_table().update_item(
            Key={"notification_id": notification_id},
            UpdateExpression="SET #r = :resp, response_timestamp = :ts, #s = :responded",
            ExpressionAttributeNames={"#r": "response", "#s": "status"},
            ExpressionAttributeValues={
                ":resp": response,
                ":ts": datetime.utcnow().isoformat(),
                ":responded": "responded",
            },
        )
        return True
    except Exception as e:
        logger.error(f"Failed to record response: {e}")
        return False


def get_donor_response(request_id: str, donor_id: str) -> Optional[str]:
    """Check whether a donor has responded to a specific request."""
    table = _notif_table()
    resp = table.scan(
        FilterExpression=(
            Attr("request_id").eq(request_id)
            & Attr("donor_id").eq(donor_id)
            & Attr("status").eq("responded")
        )
    )
    items = resp.get("Items", [])
    if items:
        return items[-1].get("response")
    return None
