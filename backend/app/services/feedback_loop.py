"""
Self-improvement feedback loop.

After every request closes (fulfilled/cancelled/no-show),
recalculates donor reliability scores and logs failure patterns
for Bedrock analysis.
"""
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Optional

import boto3

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("bloodbridge.feedback")

DONOR_CYCLE_DAYS = 90  # Standard eligibility cooldown after donation


def _users_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_USERS_TABLE
    )


def _notif_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_NOTIFICATIONS_TABLE
    )


def update_donor_after_outcome(
    donor_id: str,
    outcome: str,  # "donated" | "no_show" | "declined" | "rescheduled"
    request_id: str,
) -> dict:
    """
    Update donor stats based on outcome.
    Returns the updated fields as a dict.
    """
    users = _users_table()
    resp = users.get_item(Key={"user_id": donor_id})
    donor = resp.get("Item")
    if not donor:
        logger.warning(f"Donor {donor_id} not found for feedback update")
        return {}

    total_calls = int(donor.get("total_calls") or 0) + 1
    donations = int(donor.get("donations_till_date") or 0)

    update_parts = ["total_calls = :tc", "updated_at = :now"]
    values: dict = {
        ":tc": total_calls,
        ":now": datetime.utcnow().isoformat(),
    }

    if outcome == "donated":
        donations += 1
        next_eligible = str(date.today() + timedelta(days=DONOR_CYCLE_DAYS))
        update_parts += [
            "donations_till_date = :dt",
            "donated_earlier = :de",
            "last_donation_date = :ld",
            "next_eligible_date = :ne",
            "eligibility_status = :not_elig",
        ]
        values.update({
            ":dt": donations,
            ":de": True,
            ":ld": str(date.today()),
            ":ne": next_eligible,
            ":not_elig": "not eligible",
        })

    new_ratio = round(donations / total_calls, 4) if total_calls > 0 else 0.0
    update_parts.append("calls_to_donations_ratio = :ratio")
    values[":ratio"] = str(new_ratio)

    users.update_item(
        Key={"user_id": donor_id},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeValues=values,
    )

    logger.info(f"Donor {donor_id} updated: outcome={outcome}, new_ratio={new_ratio}")
    return {
        "donor_id": donor_id,
        "outcome": outcome,
        "total_calls": total_calls,
        "donations_till_date": donations,
        "calls_to_donations_ratio": new_ratio,
    }


def log_failure_pattern(
    request_id: str,
    failure_type: str,  # "no_response" | "no_show" | "no_donors" | "ngo_escalated"
    blood_group: str,
    search_radius_km: float,
    donor_id: Optional[str] = None,
) -> None:
    """Persist failure events for weekly Bedrock pattern analysis."""
    try:
        _notif_table().put_item(Item={
            "notification_id": f"FAILURE#{str(uuid.uuid4())}",
            "request_id": request_id,
            "donor_id": donor_id or "N/A",
            "channel": "system",
            "status": "failure_log",
            "failure_type": failure_type,
            "blood_group": blood_group,
            "search_radius_km": str(search_radius_km),
            "sent_at": datetime.utcnow().isoformat(),
            "message_preview": f"Failure: {failure_type} for {blood_group}",
        })
    except Exception as e:
        logger.error(f"Failed to log failure pattern: {e}")


def get_recent_failure_patterns(limit: int = 50) -> list:
    """Retrieve recent failure logs for Bedrock analysis."""
    from boto3.dynamodb.conditions import Attr
    table = _notif_table()
    resp = table.scan(
        FilterExpression=Attr("status").eq("failure_log"),
        Limit=limit,
    )
    return resp.get("Items", [])
