"""
4-stage donor matching engine.

Stage 1: Bridge donors (existing patient-donor relationships)
Stage 2: Emergency donors (eligible, compatible, within expanding radii)
Stage 3: Regional expansion (all compatible donors within 100 km)
Stage 4: NGO escalation flag (no donors found)
"""
from datetime import date
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

from app.config import get_settings
from app.utils.blood_compat import get_compatible_donors_for_recipient, get_initial_search_radius
from app.services.donor_ranker import compute_donor_score

settings = get_settings()

SEARCH_RADII_KM = [10, 25, 50, 100]


def _get_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_USERS_TABLE
    )


def match_donors(
    request_id: str,
    patient_blood_group: str,
    patient_lat: float,
    patient_lon: float,
    collection_date: date,
    bridge_id: Optional[str] = None,
    top_n: int = 5,
) -> List[dict]:
    """
    Returns a ranked list of up to top_n donor candidates.
    Each candidate carries stage, donor_score, and sub-scores.
    """
    table = _get_table()
    compatible_groups = get_compatible_donors_for_recipient(patient_blood_group)
    initial_radius = get_initial_search_radius(patient_blood_group)
    seen_ids: set[str] = set()
    candidates: list[dict] = []

    # ── Stage 1: Bridge donors ──────────────────────────────────────────────
    if bridge_id:
        resp = table.query(
            IndexName="bridge_id-index",
            KeyConditionExpression=Key("bridge_id").eq(bridge_id),
            FilterExpression=Attr("role").eq("Bridge Donor") & Attr("consent_given").eq(True),
        )
        for donor in resp.get("Items", []):
            if donor["user_id"] in seen_ids:
                continue
            scored = compute_donor_score(donor, patient_lat, patient_lon, collection_date)
            scored["stage"] = "bridge"
            scored["request_id"] = request_id
            candidates.append(scored)
            seen_ids.add(donor["user_id"])

    if len(candidates) >= top_n:
        return _sort_and_trim(candidates, top_n)

    # ── Stage 2: Emergency + Bridge donors with expanding radius ───────────
    radii = SEARCH_RADII_KM if initial_radius <= 10 else [initial_radius]
    for radius_km in radii:
        resp = table.scan(
            FilterExpression=(
                Attr("role").is_in(["Emergency Donor", "Bridge Donor"])
                & Attr("blood_group").is_in(compatible_groups)
                & Attr("eligibility_status").eq("eligible")
                & Attr("consent_given").eq(True)
            )
        )
        for donor in resp.get("Items", []):
            if donor["user_id"] in seen_ids:
                continue
            scored = compute_donor_score(donor, patient_lat, patient_lon, collection_date, radius_km)
            if scored["distance_km"] <= radius_km:
                scored["stage"] = "emergency"
                scored["search_radius_km"] = radius_km
                scored["request_id"] = request_id
                candidates.append(scored)
                seen_ids.add(donor["user_id"])

        if len(candidates) >= top_n:
            break

    if len(candidates) >= top_n:
        return _sort_and_trim(candidates, top_n)

    # ── Stage 3: Regional expansion (all roles, compatible groups) ──────────
    resp = table.scan(
        FilterExpression=(
            Attr("role").is_in(["Bridge Donor", "Emergency Donor", "Guest"])
            & Attr("blood_group").is_in(compatible_groups)
            & Attr("consent_given").eq(True)
        )
    )
    for donor in resp.get("Items", []):
        if donor["user_id"] in seen_ids:
            continue
        scored = compute_donor_score(donor, patient_lat, patient_lon, collection_date, 100)
        if scored["distance_km"] <= 100:
            scored["stage"] = "regional"
            scored["request_id"] = request_id
            candidates.append(scored)
            seen_ids.add(donor["user_id"])

    # ── Stage 4: NGO escalation ─────────────────────────────────────────────
    eligible_candidates = [c for c in candidates if c.get("is_eligible", False)]
    if not eligible_candidates:
        candidates.append({
            "user_id": "NGO_ESCALATION",
            "stage": "ngo",
            "donor_score": 0,
            "is_eligible": False,
            "request_id": request_id,
            "message": "No eligible donors found. Escalating to partner NGO network.",
        })

    return _sort_and_trim(candidates, top_n)


def _sort_and_trim(candidates: list[dict], top_n: int) -> list[dict]:
    eligible = [c for c in candidates if c.get("is_eligible", False) or c.get("stage") == "ngo"]
    sorted_candidates = sorted(eligible, key=lambda x: x.get("donor_score", 0), reverse=True)
    return sorted_candidates[:top_n] if sorted_candidates else candidates[:top_n]
