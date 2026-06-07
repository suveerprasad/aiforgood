"""
Lambda: bb-check-inventory
Step Functions calls this to check if enough blood units are available
for a request before attempting donor escalation.

Input:
  request_id, blood_group, units_needed

Output:
  inventory_available (bool), available_unit_ids (list)
"""
import sys
import os
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
INVENTORY_TABLE = os.environ.get("DYNAMODB_INVENTORY_TABLE", "bb_inventory")


def handler(event, context):
    blood_group = event.get("blood_group", "")
    units_needed = int(event.get("units_needed", 1))

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(INVENTORY_TABLE)

    try:
        resp = table.query(
            IndexName="blood_group-status-index",
            KeyConditionExpression=Key("blood_group").eq(blood_group) & Key("status").eq("Collected"),
        )
        available = resp.get("Items", [])
        unit_ids = [u["blood_unit_id"] for u in available[:units_needed]]

        logger.info(
            f"Inventory check: {blood_group} needs {units_needed}, found {len(available)} available"
        )

        return {
            **event,
            "inventory_available": len(available) >= units_needed,
            "available_unit_ids": unit_ids,
        }
    except Exception as e:
        logger.error(f"Inventory check failed: {e}")
        return {**event, "inventory_available": False, "available_unit_ids": []}
