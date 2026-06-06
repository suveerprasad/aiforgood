from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
import uuid


class RequestStatus(str, Enum):
    OPEN = "open"
    MATCHING = "matching"
    MATCHED = "matched"
    COLLECTING = "collecting"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


class UrgencyLevel(str, Enum):
    CRITICAL = "critical"   # <= 3 days
    HIGH = "high"           # 3-7 days
    STANDARD = "standard"   # > 7 days


class BloodRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str
    blood_group: str
    units_needed: int = 1
    urgency_level: UrgencyLevel = UrgencyLevel.STANDARD
    status: RequestStatus = RequestStatus.OPEN
    collection_window_start: Optional[str] = None
    collection_window_end: Optional[str] = None
    step_function_execution_arn: Optional[str] = None
    assigned_donors: Optional[List[str]] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None
    notes: Optional[str] = None


class CreateRequestInput(BaseModel):
    patient_id: str
    blood_group: str
    units_needed: int = 1
    transfusion_date: str
    notes: Optional[str] = None


class UpdateRequestInput(BaseModel):
    status: Optional[RequestStatus] = None
    notes: Optional[str] = None
