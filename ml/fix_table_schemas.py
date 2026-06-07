"""
Fix DynamoDB table schemas to match the API:

1. bb_requests — was (request_id HASH + created_at RANGE) → now (request_id HASH only)
2. bb_notifications — was (notification_id HASH + sent_at RANGE) → now (notification_id HASH only)
3. Create bb_auth_users (email HASH) if not exists

Since DynamoDB does not allow changing key schema in-place, this script:
  - Creates a new table with the correct schema
  - Copies all data from the old table
  - Deletes the old table
  - Renames the new table (by creating with original name after deletion)

Run:
    AWS_REGION=us-east-1 python3 ml/fix_table_schemas.py
"""
import os
import time
import logging
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("bloodbridge.fix_schemas")

REGION = os.getenv("AWS_REGION", "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name=REGION)
client = boto3.client("dynamodb", region_name=REGION)


def _wait_active(table_name: str, timeout=120):
    for _ in range(timeout // 3):
        try:
            desc = client.describe_table(TableName=table_name)["Table"]
            if desc["TableStatus"] == "ACTIVE":
                logger.info(f"  {table_name} is ACTIVE")
                return
        except ClientError:
            pass
        time.sleep(3)
    raise TimeoutError(f"{table_name} did not become ACTIVE within {timeout}s")


def _wait_deleted(table_name: str, timeout=120):
    for _ in range(timeout // 3):
        try:
            client.describe_table(TableName=table_name)
            time.sleep(3)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.info(f"  {table_name} deleted")
                return
    raise TimeoutError(f"{table_name} was not deleted within {timeout}s")


def _scan_all(table_name: str) -> list:
    table = dynamodb.Table(table_name)
    items = []
    resp = table.scan()
    items.extend(resp.get("Items", []))
    while resp.get("LastEvaluatedKey"):
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return items


def fix_table(table_name: str, new_schema: dict):
    """
    Recreate a table with the new key schema, preserving all items.
    """
    existing = set(client.list_tables()["TableNames"])

    if table_name not in existing:
        logger.info(f"{table_name} does not exist, creating fresh…")
        client.create_table(TableName=table_name, **new_schema)
        _wait_active(table_name)
        return

    # Check if the table already has the correct key schema
    desc = client.describe_table(TableName=table_name)["Table"]
    current_keys = [(k["AttributeName"], k["KeyType"]) for k in desc["KeySchema"]]
    new_keys = [(k["AttributeName"], k["KeyType"]) for k in new_schema["KeySchema"]]

    if current_keys == new_keys:
        logger.info(f"{table_name}: key schema already correct, skipping.")
        return

    logger.info(f"{table_name}: key schema mismatch — migrating…")
    logger.info(f"  Current: {current_keys}")
    logger.info(f"  Target:  {new_keys}")

    # 1. Scan all items
    items = _scan_all(table_name)
    logger.info(f"  Scanned {len(items)} items from {table_name}")

    # 2. Backup table name
    backup_name = f"{table_name}_backup_{int(time.time())}"

    # 3. Create new table with correct schema under backup name
    logger.info(f"  Creating {backup_name} with correct schema…")
    client.create_table(TableName=backup_name, **new_schema)
    _wait_active(backup_name)

    # 4. Write all items to backup table
    backup_table = dynamodb.Table(backup_name)
    written = 0
    with backup_table.batch_writer() as bw:
        for item in items:
            # Only keep the hash key attribute (remove sort key if present)
            bw.put_item(Item=item)
            written += 1
    logger.info(f"  Wrote {written} items to {backup_name}")

    # 5. Delete original
    logger.info(f"  Deleting original {table_name}…")
    client.delete_table(TableName=table_name)
    _wait_deleted(table_name)

    # 6. Create original with correct schema
    logger.info(f"  Recreating {table_name} with correct schema…")
    client.create_table(TableName=table_name, **new_schema)
    _wait_active(table_name)

    # 7. Copy items from backup to original
    orig_table = dynamodb.Table(table_name)
    with orig_table.batch_writer() as bw:
        for item in items:
            bw.put_item(Item=item)
    logger.info(f"  Copied {len(items)} items back to {table_name}")

    # 8. Delete backup
    logger.info(f"  Cleaning up {backup_name}…")
    client.delete_table(TableName=backup_name)
    logger.info(f"✓ {table_name} migration complete")


def ensure_auth_table():
    schema = {
        "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "email", "AttributeType": "S"}],
        "BillingMode": "PAY_PER_REQUEST",
    }
    existing = set(client.list_tables()["TableNames"])
    if "bb_auth_users" in existing:
        logger.info("bb_auth_users already exists, skipping.")
        return
    logger.info("Creating bb_auth_users…")
    client.create_table(TableName="bb_auth_users", **schema)
    _wait_active("bb_auth_users")
    logger.info("✓ bb_auth_users created")


REQUESTS_SCHEMA = {
    "KeySchema": [{"AttributeName": "request_id", "KeyType": "HASH"}],
    "AttributeDefinitions": [{"AttributeName": "request_id", "AttributeType": "S"}],
    "BillingMode": "PAY_PER_REQUEST",
}

NOTIFICATIONS_SCHEMA = {
    "KeySchema": [{"AttributeName": "notification_id", "KeyType": "HASH"}],
    "AttributeDefinitions": [{"AttributeName": "notification_id", "AttributeType": "S"}],
    "BillingMode": "PAY_PER_REQUEST",
}

if __name__ == "__main__":
    logger.info(f"Starting schema fix (region={REGION})…")
    fix_table("bb_requests", REQUESTS_SCHEMA)
    fix_table("bb_notifications", NOTIFICATIONS_SCHEMA)
    ensure_auth_table()
    logger.info("\nAll done! DynamoDB schemas are now correct.")
    logger.info("You can now restart the backend and run seed_demo_data.py --reset")
