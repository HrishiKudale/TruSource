# backend/models/farmer/marketplace_models.py

from pydantic import BaseModel, Field
from typing import Optional


class FarmerMarketInfoModel(BaseModel):
    cropId: str
    cropType: str
    farmerId: str

    listingId: Optional[str] = None
    location: Optional[str] = None
    buyerType: Optional[str] = None
    buyerName: Optional[str] = None
    expiryDate: Optional[str] = None

    # optional display fields (if present)
    offeredPrice: Optional[float] = None
    marketQuantity: Optional[float] = None
    status: Optional[str] = "pending"


class ListMarketPlaceModel(BaseModel):
    farmerId: str
    farmerName: Optional[str] = None

    cropId: str
    cropType: Optional[str] = None
    expiryDate: Optional[str] = None
    location: str

    offeredPrice: float
    quantity: float

    status: str = Field(default="pending")
    minimumOrderQuantity: Optional[float] = None
    buyerType: Optional[str] = None
    paymentTerms: Optional[str] = None
