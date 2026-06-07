"""Donor matching API — triggers Step Functions escalation workflow."""
import json
import logging
from datetime import date, datetime

import boto3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.config import get_settings
from app.services.donor_matcher import match_donors
from app.services.demand_predictor import predict_demand, get_urgency_forecast
from app.services.window_planner import plan_collection_window, get_escalation_wait_seconds
from app.services.communicator import send_donor_notification
from app.services.ai_insights import generate_donor_outreach_message
from app.models.request import UrgencyLevel

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("bloodbridge.matching")


class MatchRequest(BaseModel):
    request_id: str
    patient_id: str
    patient_blood_group: str
    patient_lat: float
    patient_lon: float
    transfusion_date: str
    bridge_id: Optional[str] = None
    top_n: int = 5


def _sf_client():
    return boto3.client("stepfunctions", region_name=settings.AWS_REGION)


def _requests_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_REQUESTS_TABLE
    )


@router.post("/match")
def trigger_matching(data: MatchRequest):
    """
    Run donor matching and launch Step Functions escalation workflow.
    Returns matched donors and the Step Functions execution ARN.
    """
    try:
        collection_date = date.fromisoformat(data.transfusion_date[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transfusion_date format.")

    _, _, urgency = plan_collection_window(collection_date)
    wait_seconds = get_escalation_wait_seconds(urgency)

    ranked = match_donors(
        request_id=data.request_id,
        patient_blood_group=data.patient_blood_group,
        patient_lat=data.patient_lat,
        patient_lon=data.patient_lon,
        collection_date=collection_date,
        bridge_id=data.bridge_id,
        top_n=data.top_n,
    )

    sfn_input = {
        "request_id": data.request_id,
        "patient_id": data.patient_id,
        "blood_group": data.patient_blood_group,
        "urgency_level": urgency.value,
        "wait_seconds": wait_seconds,
        "collection_date": str(collection_date),
        "ranked_donors": [d["user_id"] for d in ranked if d.get("user_id") != "NGO_ESCALATION"],
        "current_donor_index": 0,
        "inventory_available": False,
    }

    execution_arn = None
    notifications_sent = []

    if settings.STEP_FUNCTIONS_ARN:
        try:
            sfn_resp = _sf_client().start_execution(
                stateMachineArn=settings.STEP_FUNCTIONS_ARN,
                name=f"req-{data.request_id[:8]}-{int(datetime.utcnow().timestamp())}",
                input=json.dumps(sfn_input),
            )
            execution_arn = sfn_resp["executionArn"]
            _requests_table().update_item(
                Key={"request_id": data.request_id},
                UpdateExpression="SET step_function_execution_arn = :arn, #s = :matching",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":arn": execution_arn, ":matching": "matching"},
            )
            logger.info(f"Step Functions execution started: {execution_arn}")
        except Exception as e:
            logger.warning(f"Step Functions launch failed, using direct notification fallback: {e}")

    # Dev fallback: send notifications directly when SFN is not running
    if not execution_arn:
        top_donors = [d for d in ranked if d.get("user_id") != "NGO_ESCALATION"][:3]
        collection_date = str(date.fromisoformat(data.transfusion_date[:10]))
        for donor in top_donors:
            donor_id = donor.get("user_id", "")
            if not donor_id:
                continue
            message = generate_donor_outreach_message(
                donor_name=donor.get("name", donor_id[:8]),
                patient_city="your city",
                blood_group=data.patient_blood_group,
                collection_date=collection_date,
            )
            result = send_donor_notification(
                donor_id=donor_id,
                request_id=data.request_id,
                message=message,
                urgency=urgency.value,
            )
            notifications_sent.append({
                "donor_id": donor_id,
                "notification_id": result.get("notification_id"),
                "success": result.get("success"),
                "channel": result.get("channel"),
            })

        # Update request status to matching
        try:
            _requests_table().update_item(
                Key={"request_id": data.request_id},
                UpdateExpression="SET #s = :matching, updated_at = :now",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":matching": "matching",
                    ":now": datetime.utcnow().isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Could not update request status: {e}")

    return {
        "request_id": data.request_id,
        "urgency": urgency.value,
        "wait_seconds": wait_seconds,
        "ranked_donors": ranked,
        "step_function_execution_arn": execution_arn,
        "notifications_sent": notifications_sent,
    }


@router.get("/demand-forecast")
def get_demand_forecast(days_ahead: int = 7):
    """Return blood demand forecast grouped by blood group."""
    forecast = predict_demand(days_ahead=days_ahead)
    return {"days_ahead": days_ahead, "forecast": forecast}


@router.get("/urgency-queue")
def get_urgency_queue(days_ahead: int = 14):
    """Return upcoming patient transfusions sorted by urgency."""
    return {"upcoming": get_urgency_forecast(days_ahead=days_ahead)}


@router.get("/eligible-requests")
def eligible_requests_for_donor(donor_id: str):
    """
    Return all open/matching blood requests that a donor is compatible with.
    Each request is enriched with:
      - distance_km  (donor → patient/hospital)
      - patient_name (first name only, looked up from bb_users)
    """
    from app.utils.blood_compat import DONOR_TO_RECIPIENTS
    from app.utils.haversine import haversine
    from boto3.dynamodb.conditions import Attr

    dyn = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    users_table = dyn.Table(settings.DYNAMODB_USERS_TABLE)
    req_table   = dyn.Table(settings.DYNAMODB_REQUESTS_TABLE)

    # Get donor profile for blood group + coordinates
    donor = users_table.get_item(Key={"user_id": donor_id}).get("Item", {})
    donor_blood_group = donor.get("blood_group", "")
    if not donor_blood_group:
        return {"requests": [], "donor_blood_group": None}

    try:
        d_lat = float(donor.get("latitude") or 0)
        d_lon = float(donor.get("longitude") or 0)
    except (ValueError, TypeError):
        d_lat, d_lon = 0.0, 0.0

    can_donate_to_groups = DONOR_TO_RECIPIENTS.get(donor_blood_group, [donor_blood_group])

    # Scan open/matching requests
    resp = req_table.scan(FilterExpression=Attr("status").is_in(["open", "matching"]))
    items = resp.get("Items", [])
    while resp.get("LastEvaluatedKey"):
        resp = req_table.scan(
            FilterExpression=Attr("status").is_in(["open", "matching"]),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))

    # Filter by compatibility and enrich with distance + patient name
    compatible = []
    patient_cache: dict = {}

    for req in items:
        if req.get("blood_group") not in can_donate_to_groups:
            continue

        # Distance calculation
        try:
            p_lat = float(req.get("patient_lat") or 0)
            p_lon = float(req.get("patient_lon") or 0)
        except (ValueError, TypeError):
            p_lat, p_lon = 0.0, 0.0

        # If request has no coords, fall back to the patient's bb_users profile
        if p_lat == 0.0 and p_lon == 0.0:
            patient_id = req.get("patient_id", "")
            if patient_id:
                if patient_id not in patient_cache:
                    try:
                        _p = users_table.get_item(Key={"user_id": patient_id}).get("Item", {})
                        patient_cache[patient_id] = _p.get("name") or "Patient"
                        _plat = float(_p.get("latitude") or 0)
                        _plon = float(_p.get("longitude") or 0)
                        patient_cache[f"{patient_id}__lat"] = _plat
                        patient_cache[f"{patient_id}__lon"] = _plon
                    except Exception:
                        patient_cache[patient_id] = "Patient"
                        patient_cache[f"{patient_id}__lat"] = 0.0
                        patient_cache[f"{patient_id}__lon"] = 0.0
                p_lat = patient_cache.get(f"{patient_id}__lat", 0.0)
                p_lon = patient_cache.get(f"{patient_id}__lon", 0.0)

        # If donor has no location, treat as same location (0 km)
        if d_lat == 0.0 and d_lon == 0.0:
            distance_km = 0.0
        elif p_lat == 0.0 and p_lon == 0.0:
            distance_km = None          # patient location still unknown
        else:
            distance_km = round(haversine(d_lat, d_lon, p_lat, p_lon), 1)

        # Patient name (first name only for privacy) — may already be cached above
        patient_id = req.get("patient_id", "")
        if patient_id and patient_id not in patient_cache:
            try:
                _p = users_table.get_item(Key={"user_id": patient_id}).get("Item", {})
                patient_cache[patient_id] = _p.get("name") or "Patient"
                patient_cache[f"{patient_id}__lat"] = float(_p.get("latitude") or 0)
                patient_cache[f"{patient_id}__lon"] = float(_p.get("longitude") or 0)
            except Exception:
                patient_cache[patient_id] = "Patient"
        patient_display_name = patient_cache.get(patient_id, "Patient")
        # Only show first name for privacy
        patient_first_name = patient_display_name.split()[0] if patient_display_name else "Patient"

        enriched = dict(req)
        enriched["distance_km"] = distance_km
        enriched["patient_first_name"] = patient_first_name
        compatible.append(enriched)

    # Sort: critical first, then by distance
    urgency_order = {"critical": 0, "high": 1, "standard": 2}
    compatible.sort(key=lambda x: (
        urgency_order.get(x.get("urgency_level", "standard"), 2),
        x.get("distance_km") or 9999,
    ))

    return {
        "requests": compatible,
        "count": len(compatible),
        "donor_blood_group": donor_blood_group,
        "can_donate_to": can_donate_to_groups,
        "donor_name": donor.get("name", ""),
    }
