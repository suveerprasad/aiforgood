"""Donor management API."""
import logging
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Attr, Key
from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.models.user import UserProfile, UpdateConsentInput

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("bloodbridge.donors")


def _users_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_USERS_TABLE
    )


@router.get("/{donor_id}", response_model=UserProfile)
def get_donor(donor_id: str):
    resp = _users_table().get_item(Key={"user_id": donor_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Donor not found")
    return UserProfile(**item)


@router.get("")
def list_donors(
    role: str = Query(None, description="Filter by role: Bridge Donor, Emergency Donor, Guest"),
    blood_group: str = Query(None),
    eligible_only: bool = Query(False),
    system_role: str = Query(None),
):
    table = _users_table()
    filters = []

    # By default show all donor-type users (exclude pure patients)
    if role:
        filters.append(Attr("role").eq(role))
    else:
        # Include all donor roles (from CSV data and newly registered users)
        filters.append(
            Attr("role").is_in(["Bridge Donor", "Emergency Donor", "Guest", "Volunteer"])
            | Attr("system_role").eq("donor")
        )

    if blood_group:
        filters.append(Attr("blood_group").eq(blood_group))
    if eligible_only:
        filters.append(Attr("eligibility_status").eq("eligible"))
    if system_role:
        filters.append(Attr("system_role").eq(system_role))

    expr = filters[0]
    for f in filters[1:]:
        expr = expr & f

    # Full paginated scan — never cut off records due to DynamoDB's Limit
    items = []
    kwargs: dict = {"FilterExpression": expr}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key

    items.sort(key=lambda x: float(x.get("donor_score") or 0), reverse=True)
    return {"donors": items, "count": len(items)}


@router.patch("/{donor_id}/consent")
def update_consent(donor_id: str, data: UpdateConsentInput):
    table = _users_table()
    existing = table.get_item(Key={"user_id": donor_id}).get("Item")
    if not existing:
        raise HTTPException(status_code=404, detail="Donor not found")

    table.update_item(
        Key={"user_id": donor_id},
        UpdateExpression="SET consent_given = :cg, consent_timestamp = :ts",
        ExpressionAttributeValues={
            ":cg": data.consent_given,
            ":ts": datetime.utcnow().isoformat(),
        },
    )
    return {"donor_id": donor_id, "consent_given": data.consent_given}


@router.patch("/{donor_id}/status")
def update_active_status(donor_id: str, active: bool):
    table = _users_table()
    existing = table.get_item(Key={"user_id": donor_id}).get("Item")
    if not existing:
        raise HTTPException(status_code=404, detail="Donor not found")

    table.update_item(
        Key={"user_id": donor_id},
        UpdateExpression="SET user_donation_active_status = :s, updated_at = :ts",
        ExpressionAttributeValues={
            ":s": "Active" if active else "Inactive",
            ":ts": datetime.utcnow().isoformat(),
        },
    )
    return {"donor_id": donor_id, "user_donation_active_status": "Active" if active else "Inactive"}


@router.get("/by-bridge/{bridge_id}")
def get_donors_by_bridge(bridge_id: str):
    table = _users_table()
    resp = table.query(
        IndexName="bridge_id-index",
        KeyConditionExpression=Key("bridge_id").eq(bridge_id),
    )
    return {"donors": resp.get("Items", []), "bridge_id": bridge_id}
