"""
AWS Glue Python Shell job: bloodbridge-csv-ingest
Reads Dataset.csv from S3, cleans data, creates DynamoDB tables, and loads records.

Environment variables (set in Glue job config):
  S3_BUCKET      — S3 bucket name containing Dataset.csv
  S3_KEY         — S3 object key (default: data/Dataset.csv)
  AWS_REGION     — AWS region (default: ap-south-1)
  DRY_RUN        — Set to "true" to skip DynamoDB writes
"""
import os
import sys
import csv
import json
import uuid
import logging
import io
import re
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bloodbridge.ingest")

REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "bloodbridge-data")
S3_KEY = os.getenv("S3_KEY", "data/Dataset.csv")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

TABLES = {
    "bb_users": {
        "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
        "AttributeDefinitions": [
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "role", "AttributeType": "S"},
            {"AttributeName": "blood_group", "AttributeType": "S"},
            {"AttributeName": "bridge_id", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "role-blood_group-index",
                "KeySchema": [
                    {"AttributeName": "role", "KeyType": "HASH"},
                    {"AttributeName": "blood_group", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "bridge_id-index",
                "KeySchema": [{"AttributeName": "bridge_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    "bb_requests": {
        "KeySchema": [
            {"AttributeName": "request_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "request_id", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    "bb_inventory": {
        "KeySchema": [{"AttributeName": "blood_unit_id", "KeyType": "HASH"}],
        "AttributeDefinitions": [
            {"AttributeName": "blood_unit_id", "AttributeType": "S"},
            {"AttributeName": "blood_group", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "blood_group-status-index",
                "KeySchema": [
                    {"AttributeName": "blood_group", "KeyType": "HASH"},
                    {"AttributeName": "status", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    },
    "bb_notifications": {
        "KeySchema": [
            {"AttributeName": "notification_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "notification_id", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    "bb_auth_users": {
        "KeySchema": [
            {"AttributeName": "email", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "email", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    "bb_sessions": {
        "KeySchema": [
            {"AttributeName": "donor_id", "KeyType": "HASH"},
            {"AttributeName": "session_id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "donor_id", "AttributeType": "S"},
            {"AttributeName": "session_id", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
}

UNKNOWN_BLOOD_GROUPS = {"Do not Know", ""}


def create_tables(dynamodb_client):
    """Create all 5 DynamoDB tables (on-demand billing). Migrate existing
    provisioned tables to PAY_PER_REQUEST so bulk writes don't throttle."""
    import time
    existing = set(dynamodb_client.list_tables()["TableNames"])

    for table_name, config in TABLES.items():
        if table_name in existing:
            # Migrate to on-demand if still using provisioned capacity
            desc = dynamodb_client.describe_table(TableName=table_name)["Table"]
            billing = desc.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED")
            if billing == "PROVISIONED":
                logger.info(f"Migrating {table_name} to PAY_PER_REQUEST...")
                dynamodb_client.update_table(
                    TableName=table_name,
                    BillingMode="PAY_PER_REQUEST",
                )
                # Wait for update to complete
                for _ in range(60):
                    resp = dynamodb_client.describe_table(TableName=table_name)
                    if resp["Table"]["TableStatus"] == "ACTIVE":
                        break
                    time.sleep(3)
                logger.info(f"Table {table_name} migrated to on-demand.")
            else:
                logger.info(f"Table {table_name} already exists (on-demand), skipping.")
            continue
        try:
            dynamodb_client.create_table(TableName=table_name, **config)
            logger.info(f"Created table: {table_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                logger.info(f"Table {table_name} already exists.")
            else:
                raise

    # Wait for all tables to be ACTIVE
    for table_name in TABLES:
        for _ in range(60):
            resp = dynamodb_client.describe_table(TableName=table_name)
            if resp["Table"]["TableStatus"] == "ACTIVE":
                break
            time.sleep(2)
        logger.info(f"Table {table_name} is ACTIVE")


def clean_user_id(raw: str) -> str:
    """Strip Glue CSV escape sequences from user_id hex strings."""
    cleaned = raw.strip()
    if cleaned.startswith("\\x") or (len(cleaned) > 1 and cleaned[0] == chr(0x5c) and cleaned[1] == 'x'):
        cleaned = re.sub(r"\\x", "", cleaned)
    return cleaned if cleaned else str(uuid.uuid4())


def parse_bool(val: str) -> bool:
    return str(val).lower() in ("true", "1", "yes")


def safe_int(val: str) -> int | None:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_float(val: str) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def clean_date(val: str) -> str | None:
    if not val or val.strip() in ("", "null", "None"):
        return None
    try:
        return str(val.strip()[:10])
    except Exception:
        return None


def transform_row(row: dict) -> dict | None:
    """Transform a CSV row into a DynamoDB-ready item."""
    user_id = clean_user_id(row.get("user_id", ""))
    if not user_id:
        return None

    blood_group = row.get("blood_group", "").strip()
    if blood_group in UNKNOWN_BLOOD_GROUPS:
        blood_group = "Unknown"

    bridge_id_raw = row.get("bridge_id", "").strip()
    bridge_id = clean_user_id(bridge_id_raw) if bridge_id_raw else None

    item = {
        "user_id": user_id,
        "role": row.get("role", "").strip(),
        "blood_group": blood_group,
        "gender": row.get("gender", "").strip() or None,
        "bridge_status": parse_bool(row.get("bridge_status", "false")),
        "role_status": parse_bool(row.get("role_status", "true")),
        "status": row.get("status", "active").strip() or "active",
        "user_donation_active_status": row.get("user_donation_active_status", "").strip() or "Unknown",
        "consent_given": True,
        "consent_timestamp": datetime.utcnow().isoformat(),
        "ingested_at": datetime.utcnow().isoformat(),
    }

    if bridge_id:
        item["bridge_id"] = bridge_id

    # Coordinates
    lat = safe_float(row.get("latitude", ""))
    lon = safe_float(row.get("longitude", ""))
    if lat is not None:
        item["latitude"] = str(lat)
    if lon is not None:
        item["longitude"] = str(lon)

    # Patient fields
    for field in ("bridge_blood_group", "bridge_gender"):
        val = row.get(field, "").strip()
        if val:
            item[field] = val

    qty = safe_int(row.get("quantity_required", ""))
    if qty is not None:
        item["quantity_required"] = qty

    freq = safe_int(row.get("frequency_in_days", ""))
    if freq is not None:
        item["frequency_in_days"] = freq

    for date_field in (
        "last_transfusion_date",
        "expected_next_transfusion_date",
        "last_donation_date",
        "next_eligible_date",
        "last_bridge_donation_date",
        "last_contacted_date",
    ):
        cleaned = clean_date(row.get(date_field, ""))
        if cleaned:
            item[date_field] = cleaned

    reg_date = clean_date(row.get("registration_date", ""))
    if reg_date:
        item["registration_date"] = reg_date

    # Donor fields
    for field in ("donor_type", "eligibility_status"):
        val = row.get(field, "").strip()
        if val:
            item[field] = val

    for int_field in ("donations_till_date", "total_calls", "cycle_of_donations"):
        val = safe_int(row.get(int_field, ""))
        if val is not None:
            item[int_field] = val

    ratio = safe_float(row.get("calls_to_donations_ratio", ""))
    if ratio is not None:
        item["calls_to_donations_ratio"] = str(ratio)

    donated_earlier = row.get("donated_earlier", "").strip().lower()
    if donated_earlier in ("true", "false"):
        item["donated_earlier"] = donated_earlier == "true"

    bridge_status_raw = row.get("status_of_bridge", "").strip().lower()
    if bridge_status_raw in ("true", "false"):
        item["status_of_bridge"] = bridge_status_raw == "true"

    comment = row.get("inactive_trigger_comment", "").strip()
    if comment:
        item["inactive_trigger_comment"] = comment

    return item


def batch_write(table, items: list, primary_key: str = "user_id"):
    """Write items using DynamoDB batch_writer.

    Deduplicates by primary key, then writes in chunks of 200 with a
    brief pause between chunks to stay within on-demand burst limits.
    boto3's batch_writer handles the 25-item API flush internally.
    """
    import time

    seen: dict = {}
    for item in items:
        seen[item[primary_key]] = item
    unique_items = list(seen.values())
    if len(unique_items) < len(items):
        logger.info(f"Deduped {len(items) - len(unique_items)} duplicate {primary_key}s → {len(unique_items)} unique items")

    chunk_size = 200
    total = len(unique_items)
    for start in range(0, total, chunk_size):
        chunk = unique_items[start: start + chunk_size]
        with table.batch_writer() as writer:
            for item in chunk:
                writer.put_item(Item=item)
        logger.info(f"  wrote {min(start + chunk_size, total)}/{total} items...")
        if start + chunk_size < total:
            time.sleep(0.5)


def main():
    logger.info(f"Starting ingest | bucket={S3_BUCKET} key={S3_KEY} dry_run={DRY_RUN}")

    dynamodb_client = boto3.client("dynamodb", region_name=REGION)
    dynamodb_resource = boto3.resource("dynamodb", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)

    if not DRY_RUN:
        create_tables(dynamodb_client)

    # Download CSV from S3
    logger.info("Downloading CSV from S3...")
    obj = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
    content = obj["Body"].read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    logger.info(f"CSV loaded: {len(rows)} rows")

    items = []
    skipped = 0
    role_counts: dict = {}

    for row in rows:
        item = transform_row(row)
        if item:
            role = item.get("role", "Unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
            items.append(item)
        else:
            skipped += 1

    logger.info(f"Transformed: {len(items)} items | Skipped: {skipped}")
    logger.info(f"Role distribution: {json.dumps(role_counts)}")

    if DRY_RUN:
        logger.info("DRY RUN — no DynamoDB writes.")
        return

    table = dynamodb_resource.Table("bb_users")
    logger.info("Writing to DynamoDB bb_users...")
    batch_write(table, items)
    logger.info(f"Done! {len(items)} records written to bb_users.")


if __name__ == "__main__":
    main()
