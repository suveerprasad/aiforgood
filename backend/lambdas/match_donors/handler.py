"""
Lambda: bb-match-donors
Step Functions task — runs donor_matcher and returns ranked donor list.
"""
import json
import sys
import os
from datetime import date

sys.path.insert(0, "/var/task")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.services.donor_matcher import match_donors
from app.services.window_planner import plan_collection_window, get_escalation_wait_seconds


def handler(event, context):
    """
    Input: {
        request_id, patient_id, blood_group, patient_lat, patient_lon,
        collection_date, bridge_id (optional), urgency_level (optional)
    }
    Output: { ranked_donors: [...], urgency_level, wait_seconds }
    """
    request_id = event.get("request_id", "")
    blood_group = event.get("blood_group", "")
    patient_lat = float(event.get("patient_lat", 0))
    patient_lon = float(event.get("patient_lon", 0))
    collection_date_str = event.get("collection_date", str(date.today()))
    bridge_id = event.get("bridge_id")

    try:
        collection_date = date.fromisoformat(collection_date_str[:10])
    except ValueError:
        collection_date = date.today()

    _, _, urgency = plan_collection_window(collection_date)
    wait_seconds = get_escalation_wait_seconds(urgency)

    ranked = match_donors(
        request_id=request_id,
        patient_blood_group=blood_group,
        patient_lat=patient_lat,
        patient_lon=patient_lon,
        collection_date=collection_date,
        bridge_id=bridge_id,
        top_n=5,
    )

    donor_ids = [d["user_id"] for d in ranked if d.get("user_id") != "NGO_ESCALATION"]

    return {
        "ranked_donors": donor_ids,
        "ranked_donor_details": ranked,
        "urgency_level": urgency.value,
        "wait_seconds": wait_seconds,
        "request_id": request_id,
    }
