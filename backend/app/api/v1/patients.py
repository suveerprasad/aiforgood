"""Patient-facing API: create blood requests, track status."""
import uuid
import json
import logging
from datetime import datetime, date

import boto3
from boto3.dynamodb.conditions import Attr
from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.models.request import BloodRequest, CreateRequestInput, UpdateRequestInput
from app.services.window_planner import plan_collection_window
from app.services.inventory_manager import check_inventory, reserve_inventory

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("bloodbridge.patients")


def _requests_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_REQUESTS_TABLE
    )


@router.post("/requests", response_model=BloodRequest, status_code=201)
def create_blood_request(data: CreateRequestInput):
    """
    Create a new blood request.
    - Plans collection window from transfusion_date
    - Checks existing inventory first
    - Reserves inventory units if available
    """
    try:
        transfusion_date = date.fromisoformat(data.transfusion_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transfusion_date format. Use YYYY-MM-DD.")

    window_start, window_end, urgency = plan_collection_window(transfusion_date)
    request_id = str(uuid.uuid4())

    available = check_inventory(data.blood_group, data.units_needed)
    status = "open"
    assigned_donors = []

    if len(available) >= data.units_needed:
        unit_ids = [u["blood_unit_id"] for u in available[: data.units_needed]]
        if reserve_inventory(unit_ids, request_id):
            status = "matched"
            assigned_donors = unit_ids
            logger.info(f"Request {request_id}: inventory matched ({len(unit_ids)} units)")

    item = {
        "request_id": request_id,
        "created_at": datetime.utcnow().isoformat(),
        "patient_id": data.patient_id,
        "blood_group": data.blood_group,
        "units_needed": data.units_needed,
        "urgency_level": urgency.value,
        "status": status,
        "collection_window_start": str(window_start),
        "collection_window_end": str(window_end),
        "notes": data.notes or "",
        "assigned_donors": assigned_donors,
    }

    _requests_table().put_item(Item=item)
    return BloodRequest(**item)


@router.get("/requests/{request_id}")
def get_request(request_id: str):
    resp = _requests_table().get_item(Key={"request_id": request_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    return item


@router.get("/requests")
def list_requests(
    patient_id: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50, le=200),
):
    table = _requests_table()
    filter_parts = []
    if patient_id:
        filter_parts.append(Attr("patient_id").eq(patient_id))
    if status:
        filter_parts.append(Attr("status").eq(status))

    kwargs: dict = {"Limit": limit}
    if filter_parts:
        expr = filter_parts[0]
        for part in filter_parts[1:]:
            expr = expr & part
        kwargs["FilterExpression"] = expr

    resp = table.scan(**kwargs)
    items = resp.get("Items", [])
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"requests": items, "count": len(items)}


@router.patch("/requests/{request_id}")
def update_request(request_id: str, data: UpdateRequestInput):
    table = _requests_table()
    existing = table.get_item(Key={"request_id": request_id}).get("Item")
    if not existing:
        raise HTTPException(status_code=404, detail="Request not found")

    updates = {"updated_at": datetime.utcnow().isoformat()}
    if data.status:
        updates["status"] = data.status.value
    if data.notes is not None:
        updates["notes"] = data.notes

    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
    attr_names = {f"#{k}": k for k in updates}
    attr_values = {f":{k}": v for k, v in updates.items()}

    table.update_item(
        Key={"request_id": request_id},
        UpdateExpression=expr,
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )
    return {"request_id": request_id, "updated": updates}
