"""
SageMaker Feature Store setup for BloodBridge donor scores.

Creates the bb-donor-scores Feature Group for real-time
donor score lookup during matching.

Run once during infrastructure setup.
"""
import os
import time
import boto3
import sagemaker
from sagemaker.feature_store.feature_group import FeatureGroup
from sagemaker.feature_store.feature_definition import (
    FeatureDefinition, FeatureTypeEnum
)

REGION = os.getenv("AWS_REGION", "ap-south-1")
ROLE_ARN = os.getenv("SAGEMAKER_ROLE_ARN", "")
FEATURE_GROUP_NAME = "bb-donor-scores"
S3_URI = f"s3://{os.getenv('S3_BUCKET', 'bloodbridge-data')}/feature-store/"


def create_feature_group():
    session = sagemaker.Session(boto_session=boto3.Session(region_name=REGION))
    sm_client = boto3.client("sagemaker", region_name=REGION)

    feature_definitions = [
        FeatureDefinition(feature_name="donor_id", feature_type=FeatureTypeEnum.STRING),
        FeatureDefinition(feature_name="blood_group", feature_type=FeatureTypeEnum.STRING),
        FeatureDefinition(feature_name="donor_score", feature_type=FeatureTypeEnum.FRACTIONAL),
        FeatureDefinition(feature_name="eligibility_score", feature_type=FeatureTypeEnum.FRACTIONAL),
        FeatureDefinition(feature_name="reliability_score", feature_type=FeatureTypeEnum.FRACTIONAL),
        FeatureDefinition(feature_name="response_score", feature_type=FeatureTypeEnum.FRACTIONAL),
        FeatureDefinition(feature_name="active_score", feature_type=FeatureTypeEnum.FRACTIONAL),
        FeatureDefinition(feature_name="donations_till_date", feature_type=FeatureTypeEnum.INTEGRAL),
        FeatureDefinition(feature_name="calls_to_donations_ratio", feature_type=FeatureTypeEnum.FRACTIONAL),
        FeatureDefinition(feature_name="is_eligible", feature_type=FeatureTypeEnum.STRING),
        FeatureDefinition(feature_name="EventTime", feature_type=FeatureTypeEnum.FRACTIONAL),
    ]

    fg = FeatureGroup(
        name=FEATURE_GROUP_NAME,
        feature_definitions=feature_definitions,
        sagemaker_session=session,
    )

    try:
        fg.create(
            s3_uri=S3_URI,
            record_identifier_name="donor_id",
            event_time_feature_name="EventTime",
            role_arn=ROLE_ARN,
            enable_online_store=True,
        )
        print(f"Feature group '{FEATURE_GROUP_NAME}' creation initiated.")
    except Exception as e:
        if "ResourceInUse" in str(e):
            print(f"Feature group '{FEATURE_GROUP_NAME}' already exists.")
        else:
            raise

    # Wait for active
    for _ in range(30):
        resp = sm_client.describe_feature_group(FeatureGroupName=FEATURE_GROUP_NAME)
        status = resp["FeatureGroupStatus"]
        print(f"  Status: {status}")
        if status == "Created":
            break
        time.sleep(10)

    print(f"Feature group ready: {FEATURE_GROUP_NAME}")
    return FEATURE_GROUP_NAME


def upsert_donor_score(featurestore_client, donor_id: str, scores: dict):
    """Push a donor's updated scores to the Feature Store."""
    import time as t
    record = [
        {"FeatureName": "donor_id", "ValueAsString": donor_id},
        {"FeatureName": "blood_group", "ValueAsString": scores.get("blood_group", "")},
        {"FeatureName": "donor_score", "ValueAsString": str(scores.get("donor_score", 0))},
        {"FeatureName": "eligibility_score", "ValueAsString": str(scores.get("eligibility_score", 0))},
        {"FeatureName": "reliability_score", "ValueAsString": str(scores.get("reliability_score", 0))},
        {"FeatureName": "response_score", "ValueAsString": str(scores.get("response_score", 0))},
        {"FeatureName": "active_score", "ValueAsString": str(scores.get("active_score", 0))},
        {"FeatureName": "donations_till_date", "ValueAsString": str(scores.get("donations_till_date", 0))},
        {"FeatureName": "calls_to_donations_ratio", "ValueAsString": str(scores.get("calls_to_donations_ratio", 0))},
        {"FeatureName": "is_eligible", "ValueAsString": str(scores.get("is_eligible", False)).lower()},
        {"FeatureName": "EventTime", "ValueAsString": str(t.time())},
    ]
    featurestore_client.put_record(
        FeatureGroupName=FEATURE_GROUP_NAME,
        Record=record,
    )


if __name__ == "__main__":
    create_feature_group()
