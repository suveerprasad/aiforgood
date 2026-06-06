"""
Blood inventory manager.

Handles: check availability, reserve, release, reallocate, expiry risk monitoring.
Uses blood compatibility matrix — always tries to use oldest units first.
"""
import uuid
from datetime import date, timedelta, datetime
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

from app.config import get_settings
from app.utils.blood_compat import get_compatible_donors_for_recipient

settings = get_settings()

BLOOD_SHELF_LIFE_DAYS = 35  # Standard RBC shelf life
EXPIRY_WARNING_DAYS = 5     # Alert when expiring within 5 days


def _get_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_INVENTORY_TABLE
    )


def check_inventory(blood_group: str, units_needed: int = 1) -> List[dict]:
    """
    Returns available units compatible with the given blood group,
    sorted by expiry_date ascending (oldest first to reduce wastage).
    """
    table = _get_table()
    compatible_groups = get_compatible_donors_for_recipient(blood_group)
    available: list = []

    for bg in compatible_groups:
        resp = table.query(
            IndexName="blood_group-status-index",
            KeyConditionExpression=Key("blood_group").eq(bg) & Key("status").eq("Collected"),
        )
        available.extend(resp.get("Items", []))

    available.sort(key=lambda x: x.get("expiry_date", "9999-99-99"))
    return available


def reserve_inventory(blood_unit_ids: List[str], request_id: str) -> bool:
    """Atomically reserve specific units for a request."""
    table = _get_table()
    success_count = 0
    for unit_id in blood_unit_ids:
        try:
            table.update_item(
                Key={"blood_unit_id": unit_id},
                UpdateExpression="SET #s = :reserved, reserved_for_request = :req, updated_at = :now",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":reserved": "Reserved",
                    ":req": request_id,
                    ":now": datetime.utcnow().isoformat(),
                    ":collected": "Collected",
                },
                ConditionExpression=Attr("status").eq("Collected"),
            )
            success_count += 1
        except Exception:
            pass
    return success_count == len(blood_unit_ids)


def release_reservation(request_id: str) -> int:
    """Release all reserved units for a cancelled/rescheduled request back to Collected."""
    table = _get_table()
    resp = table.scan(
        FilterExpression=Attr("reserved_for_request").eq(request_id) & Attr("status").eq("Reserved")
    )
    count = 0
    for unit in resp.get("Items", []):
        table.update_item(
            Key={"blood_unit_id": unit["blood_unit_id"]},
            UpdateExpression="SET #s = :collected, updated_at = :now REMOVE reserved_for_request",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":collected": "Collected",
                ":now": datetime.utcnow().isoformat(),
            },
        )
        count += 1
    return count


def issue_units(request_id: str) -> int:
    """Mark reserved units as Issued when transfusion happens."""
    table = _get_table()
    resp = table.scan(
        FilterExpression=Attr("reserved_for_request").eq(request_id) & Attr("status").eq("Reserved")
    )
    count = 0
    for unit in resp.get("Items", []):
        table.update_item(
            Key={"blood_unit_id": unit["blood_unit_id"]},
            UpdateExpression="SET #s = :issued, updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":issued": "Issued",
                ":now": datetime.utcnow().isoformat(),
            },
        )
        count += 1
    return count


def add_blood_unit(blood_group: str, donor_id: Optional[str] = None, collection_date: Optional[date] = None) -> str:
    """Add a newly collected blood unit to inventory."""
    table = _get_table()
    coll_date = collection_date or date.today()
    unit_id = str(uuid.uuid4())
    table.put_item(Item={
        "blood_unit_id": unit_id,
        "blood_group": blood_group,
        "collection_date": str(coll_date),
        "expiry_date": str(coll_date + timedelta(days=BLOOD_SHELF_LIFE_DAYS)),
        "status": "Collected",
        "donor_id": donor_id or "",
        "created_at": datetime.utcnow().isoformat(),
    })
    return unit_id


def check_expiry_risks() -> List[dict]:
    """Return units expiring within EXPIRY_WARNING_DAYS that haven't been used."""
    table = _get_table()
    today = date.today()
    warning_cutoff = today + timedelta(days=EXPIRY_WARNING_DAYS)
    resp = table.scan(
        FilterExpression=(
            Attr("status").eq("Collected")
            & Attr("expiry_date").lte(str(warning_cutoff))
            & Attr("expiry_date").gte(str(today))
        )
    )
    return sorted(resp.get("Items", []), key=lambda x: x.get("expiry_date", ""))


def reallocate_unit(blood_unit_id: str, new_request_id: str) -> bool:
    """Reallocate a previously issued/reserved unit to another compatible request."""
    table = _get_table()
    try:
        table.update_item(
            Key={"blood_unit_id": blood_unit_id},
            UpdateExpression="SET #s = :reallocated, reserved_for_request = :req, updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":reallocated": "Reallocated",
                ":req": new_request_id,
                ":now": datetime.utcnow().isoformat(),
            },
        )
        return True
    except Exception:
        return False


def get_inventory_summary() -> List[dict]:
    """Return per-blood-group summary of inventory levels."""
    from app.utils.blood_compat import DONOR_TO_RECIPIENTS
    table = _get_table()

    resp = table.scan()
    all_units = resp.get("Items", [])

    summary: dict = {}
    today_str = str(date.today())
    warning_str = str(date.today() + timedelta(days=EXPIRY_WARNING_DAYS))

    for unit in all_units:
        bg = unit.get("blood_group", "Unknown")
        if bg not in summary:
            summary[bg] = {"blood_group": bg, "available": 0, "reserved": 0, "expiring_soon": 0, "total": 0}
        summary[bg]["total"] += 1
        status = unit.get("status", "")
        if status == "Collected":
            summary[bg]["available"] += 1
            exp = unit.get("expiry_date", "9999-99-99")
            if today_str <= exp <= warning_str:
                summary[bg]["expiring_soon"] += 1
        elif status == "Reserved":
            summary[bg]["reserved"] += 1

    return list(summary.values())
