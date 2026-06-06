import os
import json
import boto3
from functools import lru_cache


class Settings:
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SECRET_NAME: str = os.getenv("SECRET_NAME", "bloodbridge/config")

    # DynamoDB tables
    DYNAMODB_USERS_TABLE: str = "bb_users"
    DYNAMODB_REQUESTS_TABLE: str = "bb_requests"
    DYNAMODB_INVENTORY_TABLE: str = "bb_inventory"
    DYNAMODB_NOTIFICATIONS_TABLE: str = "bb_notifications"
    DYNAMODB_SESSIONS_TABLE: str = "bb_sessions"

    # AI
    BEDROCK_MODEL_ID: str = "anthropic.claude-sonnet-4-5"

    # Communication
    SES_SENDER_EMAIL: str = "noreply@bloodbridge.ai"
    SNS_SMS_SENDER_ID: str = "BloodBridge"

    # Step Functions
    STEP_FUNCTIONS_ARN: str = ""
    STEP_FUNCTIONS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")

    # SageMaker
    SAGEMAKER_FEATURE_GROUP: str = "bb-donor-scores"
    SAGEMAKER_ROLE_ARN: str = ""

    # Lex
    LEX_BOT_ID: str = ""
    LEX_BOT_ALIAS_ID: str = ""

    # CORS
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    def __init__(self):
        if self.ENVIRONMENT == "production":
            self._load_from_secrets_manager()

    def _load_from_secrets_manager(self):
        try:
            client = boto3.client("secretsmanager", region_name=self.AWS_REGION)
            response = client.get_secret_value(SecretId=self.SECRET_NAME)
            secrets = json.loads(response["SecretString"])
            for key, value in secrets.items():
                if hasattr(self, key):
                    setattr(self, key, value)
        except Exception as e:
            print(f"[config] Secrets Manager unavailable, using env vars: {e}")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
