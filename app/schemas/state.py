from pydantic import BaseModel, Field, UUID4
from typing import Optional, List
from datetime import datetime

class CharacterState(BaseModel):
    name: str
    hp: int = Field(ge=0, description="Hit points, must be non-negative")
    level: int = Field(default=1, gt=0)
    inventory: List[str] = []
    status_effects: List[str] = []

class GameState(BaseModel):
    session_id: UUID4
    character: CharacterState
    location: str
    rolling_summary: str = Field(..., description="Condensed narrative context")
    turn_count: int = Field(default=0, ge=0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
