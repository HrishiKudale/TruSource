# backend/models/farmer/lot_models.py
from pydantic import BaseModel, Field
from typing import Optional, List


class CompositeLotPrimaryModel(BaseModel):
    cropId: str
    cropType: str
    harvestDate: Optional[str]
    coaUrl: Optional[str]


class CompositeLotComponentModel(BaseModel):
    supplierFarmerId: str
    cropId: str
    cropType: str
    harvestDate: Optional[str]
    qtyKg: float
    coaUrl: Optional[str]
    invoiceNo: Optional[str]
    transportDoc: Optional[str]


class CompositeLotCreateModel(BaseModel):
    manufacturerId: str
    orderRef: Optional[str] = None
    deliveryLocation: Optional[str] = None

    committedQtyKg: float
    harvestedQtyKg: float
    shortfallKg: Optional[float] = 0

    primary: CompositeLotPrimaryModel
    components: List[CompositeLotComponentModel] = Field(default_factory=list)

    reason: Optional[str] = None
    notes: Optional[str] = None
