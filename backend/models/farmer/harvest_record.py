# backend/models/farmer/harvest_record.py
from pydantic import BaseModel, Field
from typing import Optional, List


class HarvestBagModel(BaseModel):
    epc: str
    bagQty: float
    timestamp: Optional[str]


class HarvestRecordModel(BaseModel):
    farmerId: str
    cropId: str

    harvestDate: str
    harvesterName: Optional[str]
    harvestQuantity: float
    packagingType: Optional[str]


