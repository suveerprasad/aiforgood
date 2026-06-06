from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from enum import Enum


class Role(str, Enum):
    PATIENT = "Patient"
    BRIDGE_DONOR = "Bridge Donor"
    EMERGENCY_DONOR = "Emergency Donor"
    GUEST = "Guest"
    VOLUNTEER = "Volunteer"


class DonorType(str, Enum):
    REGULAR = "Regular Donor"
    ONE_TIME = "One-Time Donor"
    OTHER = "Other"


class ActiveStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not eligible"


class UserProfile(BaseModel):
    user_id: str
    bridge_id: Optional[str] = None
    role: Role
    role_status: bool = True
    bridge_status: bool = False
    blood_group: str
    gender: Optional[str] = None
    latitude: float = 0.0
    longitude: float = 0.0
    bridge_gender: Optional[str] = None
    bridge_blood_group: Optional[str] = None
    quantity_required: Optional[int] = None
    last_transfusion_date: Optional[str] = None
    expected_next_transfusion_date: Optional[str] = None
    registration_date: Optional[str] = None
    donor_type: Optional[DonorType] = None
    last_contacted_date: Optional[str] = None
    last_donation_date: Optional[str] = None
    next_eligible_date: Optional[str] = None
    donations_till_date: Optional[int] = None
    eligibility_status: Optional[EligibilityStatus] = None
    cycle_of_donations: Optional[int] = None
    total_calls: Optional[int] = None
    frequency_in_days: Optional[int] = None
    status_of_bridge: Optional[bool] = None
    status: Optional[str] = "active"
    donated_earlier: Optional[bool] = None
    last_bridge_donation_date: Optional[str] = None
    calls_to_donations_ratio: Optional[float] = None
    user_donation_active_status: Optional[ActiveStatus] = None
    inactive_trigger_comment: Optional[str] = None
    consent_given: bool = True
    consent_timestamp: Optional[str] = None
    donor_score: Optional[float] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None


class DonorScoreResponse(BaseModel):
    user_id: str
    blood_group: str
    donor_score: float
    eligibility_score: float
    reliability_score: float
    distance_km: float
    response_score: float
    active_score: float
    distance_score: float
    stage: Optional[str] = None
    search_radius_km: Optional[float] = None


class UpdateConsentInput(BaseModel):
    consent_given: bool


class UserListResponse(BaseModel):
    users: list
    count: int
    last_evaluated_key: Optional[str] = None
