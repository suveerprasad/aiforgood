"""
Seed script for BloodBridge AI demo data.

1. Updates Patient records in bb_users with future transfusion dates
   (recalculated from last_transfusion_date + frequency_in_days)
2. Seeds bb_inventory with realistic blood unit records
3. Seeds bb_requests with active patient requests

Run:
    AWS_REGION=us-east-1 python3 ml/seed_demo_data.py
"""
import os
import uuid
import logging
from datetime import date, timedelta, datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bloodbridge.seed")

REGION = os.getenv("AWS_REGION", "us-east-1")
TODAY = date.today()

dynamodb = boto3.resource("dynamodb", region_name=REGION)

BLOOD_GROUPS = [
    "O Positive", "O Negative",
    "A Positive", "A Negative",
    "B Positive", "B Negative",
    "AB Positive", "AB Negative",
]


# ── 1. Fix Patient transfusion dates ─────────────────────────────────────────

def refresh_patient_dates():
    """
    For every Patient in bb_users:
    - If they have last_transfusion_date + frequency_in_days, compute a future
      expected_next_transfusion_date relative to today so they appear in forecasts.
    - Patients without a frequency get a random date 1–30 days from now.
    """
    table = dynamodb.Table("bb_users")

    resp = table.scan(FilterExpression=Attr("role").eq("Patient"))
    patients = resp.get("Items", [])
    while resp.get("LastEvaluatedKey"):
        resp = table.scan(
            FilterExpression=Attr("role").eq("Patient"),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        patients.extend(resp.get("Items", []))

    logger.info(f"Found {len(patients)} Patient records in bb_users")

    import random
    random.seed(42)
    updated = 0

    for patient in patients:
        freq = int(patient.get("frequency_in_days") or 0)
        if freq > 0:
            # Spread transfusion dates across the next `freq` days cycle
            days_offset = random.randint(1, max(freq, 30))
        else:
            days_offset = random.randint(1, 30)

        new_date = str(TODAY + timedelta(days=days_offset))

        table.update_item(
            Key={"user_id": patient["user_id"]},
            UpdateExpression="SET expected_next_transfusion_date = :d",
            ExpressionAttributeValues={":d": new_date},
        )
        updated += 1

    logger.info(f"Updated {updated} patients with future transfusion dates")


# ── 2. Seed bb_inventory ──────────────────────────────────────────────────────

INVENTORY_SEED = [
    # blood_group,   units,  days_until_expiry
    ("O Positive",   12,     35),
    ("O Negative",    4,     28),
    ("A Positive",    8,     42),
    ("A Negative",    3,     20),
    ("B Positive",    6,     38),
    ("B Negative",    2,     15),
    ("AB Positive",   5,     45),
    ("AB Negative",   2,     10),
    # A few near-expiry units to trigger alerts
    ("O Positive",    2,      3),
    ("A Positive",    1,      2),
    ("B Positive",    1,      4),
]


def seed_inventory():
    table = dynamodb.Table("bb_inventory")

    # Check if already seeded
    existing = table.scan(Select="COUNT")
    if existing.get("Count", 0) > 0:
        logger.info(f"bb_inventory already has {existing['Count']} units — skipping seed")
        return

    items = []
    for blood_group, units, days_to_expiry in INVENTORY_SEED:
        for _ in range(units):
            expiry = str(TODAY + timedelta(days=days_to_expiry))
            collected = str(TODAY - timedelta(days=42 - days_to_expiry))
            items.append({
                "blood_unit_id": str(uuid.uuid4()),
                "blood_group": blood_group,
                "status": "Collected",
                "expiry_date": expiry,
                "collection_date": collected,
                "location": "Hyderabad Central Blood Bank",
                "created_at": datetime.utcnow().isoformat(),
            })

    with table.batch_writer() as writer:
        for item in items:
            # Remove None values — DynamoDB rejects null attribute values
            clean = {k: v for k, v in item.items() if v is not None}
            writer.put_item(Item=clean)

    logger.info(f"Seeded {len(items)} blood units into bb_inventory")


# ── 3. Seed bb_requests ───────────────────────────────────────────────────────

REQUEST_SEED = [
    # patient_blood_group,  units, urgency_level,  days_until_transfusion
    ("O Positive",  2, "critical",  1),
    ("A Positive",  1, "critical",  2),
    ("B Positive",  2, "high",      5),
    ("O Negative",  1, "high",      6),
    ("AB Positive", 2, "standard", 10),
    ("A Negative",  1, "standard", 12),
    ("O Positive",  3, "critical",  0),
    ("B Negative",  1, "high",      4),
]


def _calc_window(transfusion_date: date):
    """Mirror window_planner logic for seeded requests."""
    days_until = (transfusion_date - TODAY).days
    if days_until <= 1:
        return str(TODAY), str(TODAY + timedelta(days=1))
    elif days_until <= 3:
        return str(TODAY), str(TODAY + timedelta(days=days_until - 1))
    else:
        window_start = transfusion_date - timedelta(days=min(days_until - 1, 7))
        window_end = transfusion_date - timedelta(days=1)
        return str(window_start), str(window_end)


def seed_requests():
    table = dynamodb.Table("bb_requests")

    existing = table.scan(Select="COUNT")
    if existing.get("Count", 0) > 0:
        logger.info(f"bb_requests already has {existing['Count']} records — skipping seed")
        return

    now = datetime.utcnow().isoformat()
    items = []
    for bg, units, urgency_level, days_offset in REQUEST_SEED:
        transfusion_date = TODAY + timedelta(days=max(days_offset, 0))
        window_start, window_end = _calc_window(transfusion_date)
        items.append({
            "request_id": str(uuid.uuid4()),
            "created_at": now,
            "patient_id": f"demo-patient-{uuid.uuid4().hex[:8]}",
            "blood_group": bg,
            "units_needed": units,
            "urgency_level": urgency_level,
            "transfusion_date": str(transfusion_date),
            "collection_window_start": window_start,
            "collection_window_end": window_end,
            "status": "open",
            "notes": "",
            "assigned_donors": [],
            "patient_lat": Decimal("17.3850"),
            "patient_lon": Decimal("78.4867"),
            "hospital": "Hyderabad Demo Hospital",
        })

    with table.batch_writer() as writer:
        for item in items:
            writer.put_item(Item=item)

    logger.info(f"Seeded {len(items)} requests into bb_requests")


def reset_table(table_name: str):
    """Delete all items from a table (use only on small tables for demo reset)."""
    table = dynamodb.Table(table_name)
    resp = table.scan()
    items = resp.get("Items", [])
    key_names = [k["AttributeName"] for k in table.key_schema]
    with table.batch_writer() as writer:
        for item in items:
            writer.delete_item(Key={k: item[k] for k in key_names})
    logger.info(f"Cleared {len(items)} items from {table_name}")


if __name__ == "__main__":
    import sys
    reset = "--reset" in sys.argv
    if reset:
        logger.info("Reset mode: clearing bb_inventory and bb_requests first")
        reset_table("bb_inventory")
        reset_table("bb_requests")

    logger.info(f"Seeding demo data (region={REGION}, today={TODAY})")
    refresh_patient_dates()
    seed_inventory()
    seed_requests()
    logger.info("Done! Re-run the API endpoints to see populated data.")
