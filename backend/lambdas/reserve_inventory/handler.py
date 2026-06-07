"""
Lambda: bb-reserve-inventory
Reserves specific blood units for a request.
Called by Step Functions when inventory is available.

Input:
  request_id, available_unit_ids (list)

Output:
  reserved (bool), reserved_unit_ids (list)
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
INVENTORY_TABLE = os.environ.get("DYNAMODB_INVENTORY_TABLE", "bb_inventory")
REQUESTS_TABLE = os.environ.get("DYNAMODB_REQUESTS_TABLE", "bb_requests")


def handler(event, context):
    request_id = event.get("request_id", "")
    unit_ids = event.get("available_unit_ids", [])

    if not unit_ids or not request_id:
        return {**event, "reserved": False, "reserved_unit_ids": []}

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    inv_table = dynamodb.Table(INVENTORY_TABLE)
    req_table = dynamodb.Table(REQUESTS_TABLE)
    now = datetime.utcnow().isoformat()

    reserved = []
    for unit_id in unit_ids:
        try:
            inv_table.update_item(
                Key={"blood_unit_id": unit_id},
                UpdateExpression="SET #s = :reserved, reserved_for = :rid, reserved_at = :now",
                ConditionExpression="attribute_exists(blood_unit_id) AND #s = :collected",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":reserved": "Reserved",
                    ":collected": "Collected",
                    ":rid": request_id,
                    ":now": now,
                },
            )
            reserved.append(unit_id)
        except Exception as e:
            logger.warning(f"Could not reserve unit {unit_id}: {e}")

    success = len(reserved) == len(unit_ids)

    if success:
        try:
            req_table.update_item(
                Key={"request_id": request_id},
                UpdateExpression="SET #s = :matched, assigned_donors = :units, updated_at = :now",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":matched": "matched",
                    ":units": reserved,
                    ":now": now,
                },
            )
        except Exception as e:
            logger.error(f"Failed to update request status: {e}")

    logger.info(f"Reserved {len(reserved)}/{len(unit_ids)} units for request {request_id}")
    return {**event, "reserved": success, "reserved_unit_ids": reserved}
