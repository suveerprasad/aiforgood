"""
Lambda: bb-feedback-loop
Step Functions final task — updates donor scores and logs failure patterns
for the self-improvement cycle.
"""
import sys
import os

sys.path.insert(0, "/var/task")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.services.feedback_loop import update_donor_after_outcome, log_failure_pattern
from app.config import get_settings

settings = get_settings()


def handler(event, context):
    """
    Input: {
        request_id, blood_group, outcome (optional),
        ranked_donors (optional), current_donor_index (optional),
        response_result.Payload.response (optional)
    }
    """
    request_id = event.get("request_id", "")
    blood_group = event.get("blood_group", "")
    outcome = event.get("outcome", "")

    # Determine outcome from Step Functions chain if not explicitly set
    if not outcome:
        response_result = (event.get("response_result") or {}).get("Payload", {})
        raw_response = response_result.get("response", "no_response")
        if raw_response in ("confirmed", "donated"):
            outcome = "donated"
        elif raw_response == "declined":
            outcome = "declined"
        elif raw_response == "rescheduled":
            outcome = "rescheduled"
        else:
            outcome = "no_response"

    ranked_donors = event.get("ranked_donors", [])
    donor_index = int(event.get("current_donor_index", 0))

    results = []

    # Update the donor who was contacted
    if ranked_donors and donor_index < len(ranked_donors):
        donor_id = ranked_donors[donor_index]
        if donor_id and donor_id != "NGO_ESCALATION":
            result = update_donor_after_outcome(donor_id, outcome, request_id)
            results.append(result)

    # Log failure patterns for no-shows and NGO escalations
    if outcome in ("no_response", "no_show", "ngo_escalated"):
        log_failure_pattern(
            request_id=request_id,
            failure_type=outcome,
            blood_group=blood_group,
            search_radius_km=100,
            donor_id=ranked_donors[donor_index] if ranked_donors and donor_index < len(ranked_donors) else None,
        )

    return {
        "status": "feedback_recorded",
        "outcome": outcome,
        "request_id": request_id,
        "updates": results,
    }
