# backend/models/farmer/recall_models.py
from pydantic import BaseModel
from typing import Optional


class RecallEventModel(BaseModel):
    recallId: str
    cropId: str
    reason: str
    timestamp: str
    manufacturerId: Optional[str]
    notes: Optional[str]
