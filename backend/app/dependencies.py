import boto3
from functools import lru_cache
from app.config import get_settings

settings = get_settings()


@lru_cache()
def get_dynamodb_resource():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION)


def get_dynamodb_client():
    return boto3.client("dynamodb", region_name=settings.AWS_REGION)


def get_bedrock_client():
    return boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def get_ses_client():
    return boto3.client("ses", region_name=settings.AWS_REGION)


def get_sns_client():
    return boto3.client("sns", region_name=settings.AWS_REGION)


def get_step_functions_client():
    return boto3.client("stepfunctions", region_name=settings.AWS_REGION)


def get_sagemaker_featurestore_client():
    return boto3.client("sagemaker-featurestore-runtime", region_name=settings.AWS_REGION)


def get_lex_client():
    return boto3.client("lexv2-runtime", region_name=settings.AWS_REGION)


def get_table(table_name: str):
    return get_dynamodb_resource().Table(table_name)
