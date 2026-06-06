"""
AI insights and message generation using Amazon Bedrock (Claude Sonnet).
"""
import json
import logging
from typing import Optional

import boto3

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("bloodbridge.ai")


def _bedrock():
    return boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def _invoke(prompt: str, max_tokens: int = 400) -> str:
    """Helper to call Claude via Bedrock and return the response text."""
    try:
        response = _bedrock().invoke_model(
            modelId=settings.BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"].strip()
    except Exception as e:
        logger.error(f"Bedrock invocation failed: {e}")
        return ""


def generate_donor_outreach_message(
    donor_name: str,
    patient_city: str,
    blood_group: str,
    collection_date: str,
    condition: str = "thalassemia",
    session_history: Optional[list] = None,
) -> str:
    """
    Generate a personalised donor outreach message.
    Incorporates last 3 turns of conversation history when available.
    """
    history_block = ""
    if session_history:
        recent = session_history[-3:]
        history_block = "\nPrevious interaction:\n" + "\n".join(
            f"{t['speaker'].title()}: {t['text']}" for t in recent
        )

    prompt = f"""You are a compassionate coordinator for Blood Warriors, an NGO that supports thalassemia patients across India.

Write a warm, concise outreach message (under 160 characters, SMS-safe) to a blood donor.

Donor first name: {donor_name}
Patient location: {patient_city}
Required blood group: {blood_group}
Preferred collection date: {collection_date}
Patient condition: {condition}{history_block}

Rules:
- Address donor by first name only
- Be warm but urgent
- Mention the patient condition briefly
- End with a clear call-to-action
- Output only the message text, nothing else"""

    msg = _invoke(prompt, max_tokens=200)
    if not msg:
        # Fallback template
        msg = (f"Hi {donor_name}, a {condition} patient in {patient_city} urgently needs {blood_group} blood "
               f"by {collection_date}. Your donation can save a life. Reply YES to confirm.")
    return msg


def generate_followup_reminder(
    donor_name: str,
    blood_group: str,
    days_remaining: int,
    attempt_number: int,
) -> str:
    """Generate an escalating follow-up reminder."""
    tone = "gentle" if attempt_number == 1 else "more urgent"
    prompt = f"""Write a {tone} follow-up reminder SMS (under 160 characters) to a blood donor.

Donor: {donor_name}
Blood group needed: {blood_group}
Days until transfusion: {days_remaining}
This is reminder #{attempt_number}

Output only the message text."""

    msg = _invoke(prompt, max_tokens=200)
    if not msg:
        msg = (f"Hi {donor_name}, reminder #{attempt_number}: a patient needs {blood_group} in {days_remaining} days. "
               f"Please confirm your donation. Reply YES or call us.")
    return msg


def generate_admin_insights(
    demand_forecast: dict,
    active_requests: int,
    inventory_at_risk: int,
    failure_patterns: Optional[list] = None,
) -> str:
    """Generate a weekly admin operations insight report."""
    failure_block = ""
    if failure_patterns:
        failure_block = f"\nRecent failure patterns (last 20): {json.dumps(failure_patterns[:20])}"

    prompt = f"""You are an AI analyst for BloodBridge, an autonomous blood coordination platform.

Generate a concise operations insight report for the admin team.

Data:
- 7-day blood demand forecast: {json.dumps(demand_forecast)}
- Active open requests: {active_requests}
- Blood units expiring within 5 days: {inventory_at_risk}{failure_block}

Output format: 5-7 bullet points covering:
1. Critical demand alerts
2. Inventory risk warnings
3. Donor engagement observations
4. Actionable recommendations
5. Predicted bottlenecks

Be specific with numbers. Output bullet points only."""

    return _invoke(prompt, max_tokens=600)


def analyze_failure_patterns(notifications: list) -> str:
    """Analyse donor non-response/no-show patterns to surface self-improvement insights."""
    if not notifications:
        return "No failure data available for analysis."

    prompt = f"""Analyze these blood donation request outcomes and identify failure patterns that the system should learn from.

Outcome data (last {len(notifications[:20])} records):
{json.dumps(notifications[:20])}

Identify:
1. Which donor types (Regular vs One-Time) are most reliable
2. Which blood groups have highest no-show rates
3. Common failure reasons
4. Specific protocol improvements to reduce failures
5. Donor scoring weight adjustments to recommend

Be concise and actionable. Output as numbered points."""

    return _invoke(prompt, max_tokens=500)


def generate_lex_welcome_message(donor_name: str, request_context: dict) -> str:
    """Generate the opening Lex bot message for a donor interaction."""
    prompt = f"""Write a warm, concise welcome message for a chatbot interaction with a blood donor.

Context:
- Donor name: {donor_name}
- Blood group needed: {request_context.get('blood_group')}
- Patient location: {request_context.get('patient_city', 'your city')}
- Collection date: {request_context.get('collection_date')}

The message should:
- Greet the donor by first name
- Briefly explain why they're being contacted
- Ask if they can confirm, reschedule, or decline
- Be under 200 characters

Output only the message."""

    msg = _invoke(prompt, max_tokens=200)
    if not msg:
        bg = request_context.get("blood_group", "")
        date_str = request_context.get("collection_date", "soon")
        msg = f"Hi {donor_name}! A patient needs {bg} blood by {date_str}. Can you donate? Reply: YES, RESCHEDULE, or NO."
    return msg
