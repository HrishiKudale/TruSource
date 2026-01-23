# backend/models/farmer/processing_models.py

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ProcessingRequestModel(BaseModel):

    cropId: str
    farmerId: str
    cropType: Optional[str] = None
    harvestDate: Optional[str] = None
    harvestQuantity: Optional[float] = 0

    manufacturerId: Optional[str] = None
    packagingType: Optional[str] = None
    status: str = Field(default="pending")

    # RFID & bags
    rfidEpcs: Optional[List[Dict[str, Any]]] = None
    rfidEpc: Optional[str] = None
    bagQty: Optional[int] = 0

    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None


class ProcessingOnchainEvent(BaseModel):
    """Simplified view of on-chain Processed event for a crop."""
    cropId: str
    cropType: Optional[str] = None
    manufacturerName: Optional[str] = None

    receivedDate: Optional[str] = None
    processedDate: Optional[str] = None
    packagingType: Optional[str] = None

    harvestQuantity: Optional[float] = 0
    processedQuantity: Optional[float] = 0
    batchCode: Optional[str] = None

    txTimestamp: Optional[int] = None
    txTimestampHuman: Optional[str] = None
