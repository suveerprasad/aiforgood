import json
import boto3
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    AWS_REGION: str = "us-east-1"
    ENVIRONMENT: str = "development"
    SECRET_NAME: str = "bloodbridge/config"

    # DynamoDB tables
    DYNAMODB_USERS_TABLE: str = "bb_users"
    DYNAMODB_REQUESTS_TABLE: str = "bb_requests"
    DYNAMODB_INVENTORY_TABLE: str = "bb_inventory"
    DYNAMODB_NOTIFICATIONS_TABLE: str = "bb_notifications"
    DYNAMODB_SESSIONS_TABLE: str = "bb_sessions"
    DYNAMODB_AUTH_TABLE: str = "bb_auth_users"

    # Auth / JWT
    SECRET_KEY: str = "bloodbridge-dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # AI
    BEDROCK_MODEL_ID: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    # Communication
    SES_SENDER_EMAIL: str = "noreply@bloodbridge.ai"
    SNS_SMS_SENDER_ID: str = "BloodBridge"

    # Step Functions
    STEP_FUNCTIONS_ARN: str = ""

    # SageMaker
    SAGEMAKER_FEATURE_GROUP: str = "bb-donor-scores"
    SAGEMAKER_ROLE_ARN: str = ""

    # Lex
    LEX_BOT_ID: str = ""
    LEX_BOT_ALIAS_ID: str = ""

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def load_from_secrets_manager(self):
        """Call once at startup in production to overlay Secrets Manager values."""
        if self.ENVIRONMENT != "production":
            return
        try:
            client = boto3.client("secretsmanager", region_name=self.AWS_REGION)
            response = client.get_secret_value(SecretId=self.SECRET_NAME)
            secrets = json.loads(response["SecretString"])
            for key, value in secrets.items():
                if hasattr(self, key):
                    object.__setattr__(self, key, value)
        except Exception as e:
            print(f"[config] Secrets Manager unavailable, using env vars: {e}")


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    s.load_from_secrets_manager()
    return s
