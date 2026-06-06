from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from enum import Enum
import uuid


class InventoryStatus(str, Enum):
    COLLECTED = "Collected"
    RESERVED = "Reserved"
    ISSUED = "Issued"
    EXPIRED = "Expired"
    REALLOCATED = "Reallocated"


class BloodUnit(BaseModel):
    blood_unit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    blood_group: str
    collection_date: str
    expiry_date: str
    status: InventoryStatus = InventoryStatus.COLLECTED
    reserved_for_request: Optional[str] = None
    donor_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None


class AddBloodUnitInput(BaseModel):
    blood_group: str
    donor_id: Optional[str] = None
    collection_date: Optional[str] = None


class InventorySummary(BaseModel):
    blood_group: str
    available: int
    reserved: int
    expiring_soon: int
    total: int
