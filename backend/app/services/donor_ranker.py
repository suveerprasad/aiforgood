"""
Multi-factor donor scoring algorithm.

Score = 30% Eligibility + 25% Reliability + 20% Distance + 15% Response Rate + 10% Active Status
"""
from datetime import date
from typing import Optional

from app.utils.haversine import haversine


def compute_donor_score(
    donor: dict,
    patient_lat: float,
    patient_lon: float,
    collection_date: date,
    max_radius_km: float = 100.0,
) -> dict:
    """
    Returns a scored dict for a donor candidate.
    All sub-scores are in range [0, 100]. Final score is weighted sum.
    """
    # --- 1. Eligibility (30%) ---
    eligibility_status = str(donor.get("eligibility_status", "not eligible")).lower()
    next_eligible_raw = donor.get("next_eligible_date")

    if eligibility_status == "eligible":
        eligibility_score = 100.0
    elif next_eligible_raw:
        try:
            next_eligible = date.fromisoformat(str(next_eligible_raw)[:10])
            eligibility_score = 100.0 if next_eligible <= collection_date else 0.0
        except ValueError:
            eligibility_score = 0.0
    else:
        eligibility_score = 0.0

    # --- 2. Reliability (25%) ---
    donations_raw = donor.get("donations_till_date")
    donations = int(donations_raw) if donations_raw not in (None, "", "null") else 0
    donor_type = str(donor.get("donor_type", "One-Time Donor"))
    type_multiplier = 1.2 if "Regular" in donor_type else 0.8
    reliability_score = min(donations / 10.0, 1.0) * 100.0 * type_multiplier
    reliability_score = min(reliability_score, 100.0)

    # --- 3. Distance (20%) ---
    try:
        d_lat = float(donor.get("latitude") or 0)
        d_lon = float(donor.get("longitude") or 0)
    except (ValueError, TypeError):
        d_lat, d_lon = 0.0, 0.0

    # If donor has no coordinates (both zero), treat as same city as patient
    # so newly registered donors without GPS data are still considered local
    if d_lat == 0.0 and d_lon == 0.0:
        d_lat, d_lon = patient_lat, patient_lon

    dist_km = haversine(patient_lat, patient_lon, d_lat, d_lon)
    distance_score = max(0.0, (1.0 - dist_km / max_radius_km) * 100.0)

    # --- 4. Response Rate (15%) ---
    ratio_raw = donor.get("calls_to_donations_ratio")
    if ratio_raw in (None, "", "null"):
        response_score = 50.0  # neutral for donors with no call history
    else:
        try:
            response_score = float(ratio_raw) * 100.0
        except (ValueError, TypeError):
            response_score = 50.0
    response_score = min(response_score, 100.0)

    # --- 5. Active Status (10%) ---
    active_status = str(donor.get("user_donation_active_status", "Inactive")).lower()
    donated_earlier = str(donor.get("donated_earlier", "false")).lower() in ("true", "1")
    active_score = 100.0 if active_status == "active" else 0.0
    if donated_earlier:
        active_score = min(active_score + 5.0, 100.0)

    # --- Final weighted score ---
    final_score = (
        0.30 * eligibility_score
        + 0.25 * reliability_score
        + 0.20 * distance_score
        + 0.15 * response_score
        + 0.10 * active_score
    )

    return {
        "user_id": donor["user_id"],
        "name": donor.get("name", ""),
        "phone_number": donor.get("phone_number", ""),
        "email": donor.get("email", ""),
        "blood_group": donor.get("blood_group", ""),
        "role": donor.get("role", donor.get("donor_type", "")),
        "distance_km": round(dist_km, 2),
        "donor_score": round(final_score, 2),
        "eligibility_score": round(eligibility_score, 2),
        "reliability_score": round(reliability_score, 2),
        "distance_score": round(distance_score, 2),
        "response_score": round(response_score, 2),
        "active_score": round(active_score, 2),
        "donations_count": donations,
        "is_eligible": eligibility_score > 0,
    }
