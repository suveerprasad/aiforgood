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
        except Exception as e:
            logger.warning(f"Step Functions launch failed: {e}")

    return {
        "request_id": data.request_id,
        "urgency": urgency.value,
        "wait_seconds": wait_seconds,
        "ranked_donors": ranked,
        "step_function_execution_arn": execution_arn,
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
