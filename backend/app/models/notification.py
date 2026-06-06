from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    SYSTEM = "system"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RESPONDED = "responded"


class DonorResponse(str, Enum):
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    RESCHEDULED = "rescheduled"
    NO_RESPONSE = "no_response"
    DONATED = "donated"
    NO_SHOW = "no_show"


class NotificationLog(BaseModel):
    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    donor_id: str
    request_id: str
    channel: NotificationChannel = NotificationChannel.EMAIL
    status: NotificationStatus = NotificationStatus.PENDING
    response: Optional[DonorResponse] = None
    response_timestamp: Optional[str] = None
    sent_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    message_preview: Optional[str] = None
    urgency: Optional[str] = None
