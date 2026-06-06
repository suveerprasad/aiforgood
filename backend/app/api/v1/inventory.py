"""Blood inventory management API."""
import logging
from datetime import datetime

import boto3
from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.models.inventory import BloodUnit, AddBloodUnitInput
from app.services.inventory_manager import (
    check_inventory,
    add_blood_unit,
    check_expiry_risks,
    reallocate_unit,
    issue_units,
    release_reservation,
    get_inventory_summary,
)

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("bloodbridge.inventory")


def _inv_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_INVENTORY_TABLE
    )


@router.get("/summary")
def inventory_summary():
    """Per-blood-group summary with available, reserved, expiring counts."""
    return {"summary": get_inventory_summary()}


@router.get("/check")
def check_available(blood_group: str = Query(...), units: int = Query(1)):
    """Check if enough inventory exists for a given blood group."""
    available = check_inventory(blood_group, units)
    return {
        "blood_group": blood_group,
        "units_requested": units,
        "units_available": len(available),
        "sufficient": len(available) >= units,
        "units": available[:units],
    }


@router.get("/expiry-alerts")
def expiry_alerts():
    """List blood units expiring within 5 days."""
    at_risk = check_expiry_risks()
    return {"expiring_soon": at_risk, "count": len(at_risk)}


@router.post("/units", status_code=201)
def add_unit(data: AddBloodUnitInput):
    """Add a newly collected blood unit to inventory."""
    unit_id = add_blood_unit(
        blood_group=data.blood_group,
        donor_id=data.donor_id,
        collection_date=None,
    )
    return {"blood_unit_id": unit_id, "blood_group": data.blood_group, "status": "Collected"}


@router.get("/units/{blood_unit_id}")
def get_unit(blood_unit_id: str):
    resp = _inv_table().get_item(Key={"blood_unit_id": blood_unit_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Blood unit not found")
    return item


@router.post("/units/{blood_unit_id}/reallocate")
def reallocate(blood_unit_id: str, new_request_id: str):
    """Reallocate a blood unit to a different request."""
    success = reallocate_unit(blood_unit_id, new_request_id)
    if not success:
        raise HTTPException(status_code=500, detail="Reallocation failed")
    return {"blood_unit_id": blood_unit_id, "reallocated_to": new_request_id}


@router.post("/requests/{request_id}/issue")
def issue_blood(request_id: str):
    """Mark reserved units as Issued when transfusion occurs."""
    count = issue_units(request_id)
    return {"request_id": request_id, "units_issued": count}


@router.post("/requests/{request_id}/release")
def release_blood(request_id: str):
    """Release reserved units back to available when a request is cancelled."""
    count = release_reservation(request_id)
    return {"request_id": request_id, "units_released": count}
