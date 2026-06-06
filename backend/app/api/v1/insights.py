"""AI-powered insights and admin analytics API."""
import logging
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List

from app.services.ai_insights import (
    generate_admin_insights,
    analyze_failure_patterns,
    generate_donor_outreach_message,
)
from app.services.demand_predictor import predict_demand, get_weekly_demand_trend
from app.services.inventory_manager import check_expiry_risks
from app.services.feedback_loop import get_recent_failure_patterns
from app.services.guest_outreach import run_guest_activation_campaign

router = APIRouter()
logger = logging.getLogger("bloodbridge.insights")


class OutreachRequest(BaseModel):
    donor_name: str
    patient_city: str
    blood_group: str
    collection_date: str
    condition: str = "thalassemia"
    session_history: Optional[List[dict]] = None


@router.get("/admin-summary")
def admin_summary():
    """
    AI-generated weekly ops summary for the admin dashboard.
    Combines demand forecast + inventory risk + failure patterns.
    """
    forecast = predict_demand(7)
    at_risk = check_expiry_risks()
    failure_patterns = get_recent_failure_patterns(20)

    # Count active requests from requests table
    import boto3
    from boto3.dynamodb.conditions import Attr
    from app.config import get_settings
    settings = get_settings()
    req_table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_REQUESTS_TABLE
    )
    active_count_resp = req_table.scan(
        FilterExpression=Attr("status").is_in(["open", "matching", "matched"]),
        Select="COUNT",
    )
    active_requests = active_count_resp.get("Count", 0)

    ai_text = generate_admin_insights(
        demand_forecast=forecast,
        active_requests=active_requests,
        inventory_at_risk=len(at_risk),
        failure_patterns=failure_patterns,
    )

    return {
        "demand_forecast": forecast,
        "active_requests": active_requests,
        "inventory_at_risk": len(at_risk),
        "ai_summary": ai_text,
    }


@router.get("/demand-trend")
def demand_trend():
    """Daily demand trend for the next 7 days (for charting)."""
    return {"trend": get_weekly_demand_trend()}


@router.get("/failure-analysis")
def failure_analysis():
    """Bedrock analysis of recent donor failure patterns."""
    patterns = get_recent_failure_patterns(50)
    analysis = analyze_failure_patterns(patterns)
    return {"pattern_count": len(patterns), "analysis": analysis}


@router.post("/outreach-message")
def outreach_message(data: OutreachRequest):
    """Generate a personalised donor outreach message via Bedrock."""
    message = generate_donor_outreach_message(
        donor_name=data.donor_name,
        patient_city=data.patient_city,
        blood_group=data.blood_group,
        collection_date=data.collection_date,
        condition=data.condition,
        session_history=data.session_history,
    )
    return {"message": message}


@router.post("/guest-campaign")
def run_guest_campaign(dry_run: bool = Query(False)):
    """Trigger the weekly guest activation campaign."""
    result = run_guest_activation_campaign(dry_run=dry_run)
    return result
