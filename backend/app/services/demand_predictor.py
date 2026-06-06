"""
7-day blood demand forecasting from patient transfusion schedules.
Aggregates expected_next_transfusion_date across all Patient records.
"""
from datetime import date, timedelta
from collections import defaultdict
from typing import Dict, List

import boto3
from boto3.dynamodb.conditions import Attr

from app.config import get_settings

settings = get_settings()

STANDARD_BLOOD_GROUPS = [
    "O Positive", "O Negative",
    "A Positive", "A Negative",
    "B Positive", "B Negative",
    "AB Positive", "AB Negative",
]


def _get_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_USERS_TABLE
    )


def predict_demand(days_ahead: int = 7) -> Dict[str, int]:
    """
    Scan Patient records and aggregate quantity_required by blood group
    for transfusion dates falling within the next `days_ahead` days.
    Returns { "O Positive": 12, "B Positive": 5, ... }
    """
    table = _get_table()
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    demand: dict = defaultdict(int)

    resp = table.scan(FilterExpression=Attr("role").eq("Patient"))
    pages = [resp]
    while resp.get("LastEvaluatedKey"):
        resp = table.scan(
            FilterExpression=Attr("role").eq("Patient"),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        pages.append(resp)

    for page in pages:
        for patient in page.get("Items", []):
            transfusion_raw = patient.get("expected_next_transfusion_date")
            if not transfusion_raw:
                continue
            try:
                transfusion_date = date.fromisoformat(str(transfusion_raw)[:10])
            except ValueError:
                continue
            if today <= transfusion_date <= cutoff:
                blood_group = patient.get("bridge_blood_group") or patient.get("blood_group", "Unknown")
                qty = int(patient.get("quantity_required") or 1)
                demand[blood_group] += qty

    result = {bg: demand.get(bg, 0) for bg in STANDARD_BLOOD_GROUPS}
    other = sum(v for k, v in demand.items() if k not in STANDARD_BLOOD_GROUPS)
    if other:
        result["Other"] = other
    return result


def get_urgency_forecast(days_ahead: int = 14) -> List[dict]:
    """
    Returns a list of upcoming patient transfusions sorted by days_until (ascending).
    Each entry includes urgency level.
    """
    table = _get_table()
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    upcoming: list = []
    resp = table.scan(FilterExpression=Attr("role").eq("Patient"))

    for patient in resp.get("Items", []):
        transfusion_raw = patient.get("expected_next_transfusion_date")
        if not transfusion_raw:
            continue
        try:
            transfusion_date = date.fromisoformat(str(transfusion_raw)[:10])
        except ValueError:
            continue

        days_until = (transfusion_date - today).days
        if 0 <= days_until <= days_ahead:
            if days_until <= 3:
                urgency = "critical"
            elif days_until <= 7:
                urgency = "high"
            else:
                urgency = "standard"

            upcoming.append({
                "patient_id": patient["user_id"],
                "blood_group": patient.get("bridge_blood_group") or patient.get("blood_group"),
                "bridge_id": patient.get("bridge_id"),
                "transfusion_date": str(transfusion_date),
                "days_until": days_until,
                "urgency": urgency,
                "units": int(patient.get("quantity_required") or 1),
                "frequency_in_days": patient.get("frequency_in_days"),
            })

    return sorted(upcoming, key=lambda x: x["days_until"])


def get_weekly_demand_trend() -> List[dict]:
    """Returns daily demand totals for each of the next 7 days."""
    table = _get_table()
    today = date.today()

    daily: dict = defaultdict(int)
    resp = table.scan(FilterExpression=Attr("role").eq("Patient"))

    for patient in resp.get("Items", []):
        transfusion_raw = patient.get("expected_next_transfusion_date")
        if not transfusion_raw:
            continue
        try:
            transfusion_date = date.fromisoformat(str(transfusion_raw)[:10])
        except ValueError:
            continue
        days_until = (transfusion_date - today).days
        if 0 <= days_until < 7:
            daily[str(transfusion_date)] += int(patient.get("quantity_required") or 1)

    trend = []
    for i in range(7):
        day = today + timedelta(days=i)
        trend.append({"date": str(day), "units": daily.get(str(day), 0)})
    return trend
