"""
Script to create the DonorResponseBot in Amazon Lex V2.
Run once during infrastructure setup.

Usage:
    python deploy_lex_bot.py --role-arn arn:aws:iam::ACCT:role/LexRole \
                              --fulfillment-lambda arn:aws:lambda:...:bb-lex-fulfillment
"""
import argparse
import json
import time
import boto3

import os
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

client = boto3.client("lexv2-models", region_name=REGION)


def create_bot(role_arn: str, fulfillment_lambda_arn: str) -> dict:
    print("Creating DonorResponseBot...")

    bot = client.create_bot(
        botName="DonorResponseBot",
        description="BloodBridge AI donor interaction bot",
        roleArn=role_arn,
        dataPrivacy={"childDirected": False},
        idleSessionTTLInSeconds=300,
    )
    bot_id = bot["botId"]
    print(f"Bot created: {bot_id}")

    # Wait for bot to be available
    _wait_for_bot(bot_id, "Available")

    # Create locale
    client.create_bot_locale(
        botId=bot_id,
        botVersion="DRAFT",
        localeId="en_IN",
        nluIntentConfidenceThreshold=0.4,
    )
    # Wait for locale to finish creating before adding intents
    _wait_for_locale(bot_id, "NotBuilt")

    # Create intents
    _create_intents(bot_id, fulfillment_lambda_arn)

    # Build locale
    client.build_bot_locale(botId=bot_id, botVersion="DRAFT", localeId="en_IN")
    _wait_for_locale(bot_id, "Built")

    # Create version
    version_resp = client.create_bot_version(
        botId=bot_id,
        botVersionLocaleSpecification={
            "en_IN": {"sourceBotVersion": "DRAFT"}
        },
    )
    bot_version = version_resp["botVersion"]
    _wait_for_bot_version(bot_id, bot_version)

    # Create alias
    alias_resp = client.create_bot_alias(
        botId=bot_id,
        botAliasName="production",
        botVersion=bot_version,
        botAliasLocaleSettings={
            "en_IN": {
                "enabled": True,
                "codeHookSpecification": {
                    "lambdaCodeHook": {
                        "lambdaARN": fulfillment_lambda_arn,
                        "codeHookInterfaceVersion": "1.0",
                    }
                },
            }
        },
    )
    alias_id = alias_resp["botAliasId"]

    print(f"\nDeployment complete!")
    print(f"  Bot ID:     {bot_id}")
    print(f"  Version:    {bot_version}")
    print(f"  Alias ID:   {alias_id}")
    print(f"\nUpdate apprunner.yaml / Secrets Manager with:")
    print(f"  LEX_BOT_ID={bot_id}")
    print(f"  LEX_BOT_ALIAS_ID={alias_id}")

    return {"bot_id": bot_id, "bot_version": bot_version, "alias_id": alias_id}


def _create_intents(bot_id: str, fulfillment_lambda_arn: str):
    intents_config = [
        {
            "intentName": "ConfirmDonation",
            "description": "Donor confirms they will donate blood",
            "sampleUtterances": [
                {"utterance": "Yes"},
                {"utterance": "Yes I will donate"},
                {"utterance": "I can donate"},
                {"utterance": "Confirm"},
                {"utterance": "I am available"},
                {"utterance": "Count me in"},
                {"utterance": "Sure"},
            ],
        },
        {
            "intentName": "RescheduleDonation",
            "description": "Donor wants to reschedule",
            "sampleUtterances": [
                {"utterance": "Reschedule"},
                {"utterance": "Can I change the date"},
                {"utterance": "Different date"},
                {"utterance": "Not available on that day"},
            ],
        },
        {
            "intentName": "DeclineDonation",
            "description": "Donor cannot donate",
            "sampleUtterances": [
                {"utterance": "No"},
                {"utterance": "I cannot donate"},
                {"utterance": "Not available"},
                {"utterance": "Decline"},
            ],
        },
        {
            "intentName": "AskQuestion",
            "description": "Donor asks about donation process",
            "sampleUtterances": [
                {"utterance": "Help"},
                {"utterance": "Where do I donate"},
                {"utterance": "Am I eligible"},
                {"utterance": "FAQ"},
            ],
        },
    ]

    for intent_cfg in intents_config:
        client.create_intent(
            botId=bot_id,
            botVersion="DRAFT",
            localeId="en_IN",
            **intent_cfg,
            fulfillmentCodeHook={"enabled": True},
        )
        print(f"  Intent created: {intent_cfg['intentName']}")


def _wait_for_bot(bot_id: str, target_status: str, timeout: int = 120):
    for _ in range(timeout // 5):
        resp = client.describe_bot(botId=bot_id)
        if resp["botStatus"] == target_status:
            return
        time.sleep(5)
    raise TimeoutError(f"Bot {bot_id} did not reach {target_status}")


def _wait_for_locale(bot_id: str, target_status: str, timeout: int = 300):
    for _ in range(timeout // 10):
        resp = client.describe_bot_locale(botId=bot_id, botVersion="DRAFT", localeId="en_IN")
        if resp["botLocaleStatus"] == target_status:
            return
        print(f"  Locale status: {resp['botLocaleStatus']}...")
        time.sleep(10)
    raise TimeoutError("Locale build timed out")


def _wait_for_bot_version(bot_id: str, version: str, timeout: int = 120):
    import botocore.exceptions
    time.sleep(5)  # Give AWS a moment to register the version
    for _ in range(timeout // 5):
        try:
            resp = client.describe_bot_version(botId=bot_id, botVersion=version)
            if resp["botStatus"] == "Available":
                return
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                pass  # Version not yet queryable, retry
            else:
                raise
        time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--fulfillment-lambda", required=True)
    args = parser.parse_args()
    create_bot(args.role_arn, args.fulfillment_lambda)
