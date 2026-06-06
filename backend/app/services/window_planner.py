"""
Transfusion window planner.

Calculates the optimal donor collection window given a patient's transfusion date.
Ensures fresh blood availability while reducing storage risk.
"""
from datetime import date, timedelta
from typing import Tuple

from app.models.request import UrgencyLevel


def plan_collection_window(transfusion_date: date) -> Tuple[date, date, UrgencyLevel]:
    """
    Returns (window_start, window_end, urgency_level).

    Rules:
    - Critical (≤ 3 days): collect today, window closes 1 day before transfusion
    - High (3–7 days): start today, close 2 days before transfusion
    - Standard (> 7 days): start 7 days before, close 3 days before transfusion
    """
    today = date.today()
    days_until = (transfusion_date - today).days

    if days_until <= 0:
        # Transfusion is today or overdue — emergency
        return today, today, UrgencyLevel.CRITICAL

    if days_until <= 3:
        urgency = UrgencyLevel.CRITICAL
        window_start = today
        window_end = max(today, transfusion_date - timedelta(days=1))
    elif days_until <= 7:
        urgency = UrgencyLevel.HIGH
        window_start = today
        window_end = max(today, transfusion_date - timedelta(days=2))
    else:
        urgency = UrgencyLevel.STANDARD
        window_start = transfusion_date - timedelta(days=7)
        window_end = transfusion_date - timedelta(days=3)

    window_start = max(window_start, today)
    return window_start, window_end, urgency


def get_escalation_wait_seconds(urgency: UrgencyLevel) -> int:
    """Returns the Step Functions wait duration (seconds) based on urgency."""
    return {
        UrgencyLevel.CRITICAL: 7_200,    # 2 hours
        UrgencyLevel.HIGH: 21_600,        # 6 hours
        UrgencyLevel.STANDARD: 86_400,    # 24 hours
    }[urgency]
