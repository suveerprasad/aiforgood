from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class ConversationTurn(BaseModel):
    speaker: str  # "bot" or "user"
    text: str
    timestamp: str


class LexSession(BaseModel):
    donor_id: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lex_session_attributes: Dict[str, str] = {}
    last_intent: Optional[str] = None
    conversation_history: List[ConversationTurn] = []
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class LexMessage(BaseModel):
    donor_id: str
    message: str
    session_id: Optional[str] = None
