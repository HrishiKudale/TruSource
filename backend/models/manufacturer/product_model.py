from pydantic import BaseModel,Field
from typing import Optional, List

class ProductRegistrationModel(BaseModel):
    manufacturerId: str = Field(..., description="ID of the manufacturer")
    cropId: str = Field(description="Blockchain ID of the crop")
    cropType: str
    cropName:str
    receivedQty: Optional[float] = 0
    dateReceived:Optional[str] = None
    serviceType: Optional[str] = None
    location:Optional[str]
    estimatedDate:Optional[str] = None


class ProductProcessingModel(BaseModel):
    manufacturerId: str = Field(..., description="ID of the manufacturer")
    cropId: str = Field(description="Blockchain ID of the crop")
    cropType: str
    cropName:str
    processingStage: str =""
    processedQuantity: Optional[float] = 0
    status: str = Field(default="pending")


class ProductInfoModel(BaseModel):
    cropId: str = Field(description="Blockchain ID of the crop")
    cropType: str
    cropName:str
    dateReceived:Optional[str] = None
    serviceType: Optional[str] = None
    location:Optional[str]
    estimatedDate:Optional[str] = None
    processedDate:Optional[str] = None
    receivedQty: Optional[str] = None
    processedQty: Optional[str] = None
    timestamp: Optional[str]
    status: str = Field(default="pending")
    note: str

