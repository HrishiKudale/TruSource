from pydantic import BaseModel,Field
from typing import Optional, List, Dict, Any

class PackagingRegistrationModel(BaseModel):
    manufacturerId: str = Field(..., description="ID of the manufacturer")
    cropId: str = Field(description="Blockchain ID of the crop")
    cropType: str
    cropName:str
    batchCode: Optional[str] = None
    packagedQuantity: Optional[float] = 0
    packagingType: Optional[str] = None
    rfidEpcs: Optional[List[Dict[str, Any]]] = None
    rfidEpc: Optional[str] = None

class PackagingInfoModel(BaseModel):
    cropId: str
    cropType: str
    cropName:str
    batchCode: Optional[str] = None
    packagingType: Optional[str] = None
    rfidEpcs: Optional[List[Dict[str, Any]]] = None
    rfidEpc: Optional[str] = None
    packagedQuantity: Optional[float] = 0
    description = Optional[str] = None
    price = Field(max_digits=10, decimal_places=2)
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None

