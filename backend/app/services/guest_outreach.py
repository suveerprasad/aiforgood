"""
Guest Conversion / Outreach Engine.

Weekly job that targets the 2420+ Guest accounts whose blood groups
match high-demand types, sending activation emails to convert them
into active donors.
"""
import logging
from datetime import datetime, date
import boto3
from boto3.dynamodb.conditions import Attr

from app.config import get_settings
from app.services.demand_predictor import predict_demand
from app.services.communicator import send_email

settings = get_settings()
logger = logging.getLogger("bloodbridge.guest_outreach")


def _users_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_USERS_TABLE
    )


def run_guest_activation_campaign(dry_run: bool = False) -> dict:
    """
    1. Forecast demand for next 14 days
    2. Find Guest users whose blood groups match
    3. Send activation email to each (max 50 per run, consent-gated)
    Returns stats dict.
    """
    demand = predict_demand(days_ahead=14)
    high_demand_groups = [bg for bg, units in demand.items() if units > 0]

    if not high_demand_groups:
        return {"activated": 0, "skipped": 0, "message": "No high-demand blood groups this week."}

    table = _users_table()
    resp = table.scan(
        FilterExpression=(
            Attr("role").eq("Guest")
            & Attr("blood_group").is_in(high_demand_groups)
            & Attr("consent_given").eq(True)
        )
    )
    guests = resp.get("Items", [])

    activated = 0
    skipped = 0

    for guest in guests[:50]:
        email = guest.get("email")
        if not email:
            skipped += 1
            continue

        blood_group = guest.get("blood_group", "")
        units_needed = demand.get(blood_group, 0)

        body = f"""Hi there!

Blood Warriors urgently needs {blood_group} donors this week.
There are {units_needed} patients in your area with upcoming transfusions.

As a registered member, a single donation from you could save a life.

Complete your donor profile and confirm availability:
→ https://bloodbridge.ai/donate

Thank you for being a Blood Warrior.

— BloodBridge AI Team"""

        subject = f"Urgent: {blood_group} Donors Needed Near You"

        if not dry_run:
            success = send_email(email, subject, body)
            if success:
                table.update_item(
                    Key={"user_id": guest["user_id"]},
                    UpdateExpression="SET last_contacted_date = :d",
                    ExpressionAttributeValues={":d": str(date.today())},
                )
                activated += 1
            else:
                skipped += 1
        else:
            activated += 1  # Count as "would activate" in dry run

    logger.info(f"Guest outreach: activated={activated}, skipped={skipped}, groups={high_demand_groups}")
    return {
        "activated": activated,
        "skipped": skipped,
        "high_demand_groups": high_demand_groups,
        "total_guests_targeted": len(guests),
        "dry_run": dry_run,
    }
