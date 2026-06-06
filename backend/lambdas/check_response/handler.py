"""
Lambda: bb-check-response
Step Functions task — checks whether the current donor has responded.
"""
import sys
import os
import boto3

sys.path.insert(0, "/var/task")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.services.communicator import get_donor_response
from app.config import get_settings

settings = get_settings()


def handler(event, context):
    """
    Input: { request_id, ranked_donors: [...], current_donor_index: N }
    Output: { donor_confirmed: bool, response, donor_id }
    """
    request_id = event.get("request_id", "")
    ranked_donors = event.get("ranked_donors", [])
    donor_index = int(event.get("current_donor_index", 0))

    if donor_index >= len(ranked_donors):
        return {
            "donor_confirmed": False,
            "response": "no_donors",
            "request_id": request_id,
        }

    donor_id = ranked_donors[donor_index]
    response = get_donor_response(request_id, donor_id)

    confirmed = response in ("confirmed", "donated")

    return {
        "donor_confirmed": confirmed,
        "response": response or "no_response",
        "donor_id": donor_id,
        "request_id": request_id,
        "current_donor_index": donor_index,
        "ranked_donors": ranked_donors,
    }
