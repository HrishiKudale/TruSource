from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class CropRegistrationModel(BaseModel):
    farmerId: str = Field(..., description="ID of the farmer")
    cropId: str = Field(..., description="Blockchain Crop ID")
    cropType: str
    cropName:str
    farmerName: Optional[str] = None    
    datePlanted: Optional[str] = None
    farmingType: Optional[str] = None
    seedType: Optional[str] = None
    location: Optional[str] = None        
    areaSize: Optional[float] = None
    coordinates: Optional[List[Dict[str, Any]]] = None  


class CropInfoModel(BaseModel):
    cropId: str
    cropType: str
    cropName:str
    farmingType: Optional[str]
    seedType: Optional[str]
    datePlanted: Optional[str]
    harvestDate: Optional[str]
    harvestedQty: Optional[float] = 0
    soldQty: Optional[float] = 0
    areaSize: Optional[float]
    timestamp: Optional[str]

