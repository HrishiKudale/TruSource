from pydantic import BaseModel, Field
from typing import Optional


class OperationRegistrationModel(BaseModel):
    manufacturerId: str = Field(..., description="ID of manufacturer")
    operationId: str = Field(..., description="Blockchain operation/product ID")

    cropId: str
    cropName: str
    cropType: Optional[str] = None

    sowingDate: Optional[str] = None
    harvestDate: Optional[str] = None

    totalQty: Optional[float] = 0
    requestedQty: Optional[float] = 0
    processedQty: Optional[float] = 0

    status: Optional[str] = "Requested"
    buyer: Optional[str] = None

    productName: Optional[str] = None
    manufacturerName: Optional[str] = None
    processingDate: Optional[str] = None


class OperationInfoModel(BaseModel):
    operationId: str
    cropId: str
    cropName: str
    cropType: Optional[str] = None

    sowingDate: Optional[str] = None
    harvestDate: Optional[str] = None

    totalQty: Optional[float] = 0
    requestedQty: Optional[float] = 0
    processedQty: Optional[float] = 0

    status: Optional[str] = None
    buyer: Optional[str] = None

    productName: Optional[str] = None
    manufacturerName: Optional[str] = None
    processingDate: Optional[str] = None
    timestamp: Optional[str] = None