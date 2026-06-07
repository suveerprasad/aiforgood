"""
Lambda: bb-update-request-status
Updates a blood request's status in DynamoDB.
Called by Step Functions at key workflow transitions.

Input:
  request_id, new_status (open | matching | matched | fulfilled | cancelled | escalated)
  Optional: notes, escalation_level

Output:
  updated (bool), request_id, new_status
"""
import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
REQUESTS_TABLE = os.environ.get("DYNAMODB_REQUESTS_TABLE", "bb_requests")

VALID_STATUSES = {"open", "matching", "matched", "fulfilled", "cancelled", "escalated"}


def handler(event, context):
    request_id = event.get("request_id", "")
    new_status = event.get("new_status", "")

    if not request_id or new_status not in VALID_STATUSES:
        logger.error(f"Invalid params: request_id={request_id}, new_status={new_status}")
        return {**event, "updated": False}

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(REQUESTS_TABLE)
    now = datetime.utcnow().isoformat()

    update_parts = ["#s = :status", "updated_at = :now"]
    attr_values = {":status": new_status, ":now": now}

    if event.get("notes"):
        update_parts.append("notes = :notes")
        attr_values[":notes"] = event["notes"]

    if event.get("escalation_level"):
        update_parts.append("escalation_level = :esc")
        attr_values[":esc"] = event["escalation_level"]

    try:
        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues=attr_values,
        )
        logger.info(f"Request {request_id} status → {new_status}")
        return {**event, "updated": True}
    except Exception as e:
        logger.error(f"Failed to update request {request_id}: {e}")
        return {**event, "updated": False}
