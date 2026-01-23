from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class OrderDetails(BaseModel):
    request_id: Optional[str]
    payment_terms: str
    buyer_type: str
    buyer_id: str
    buyer_name: Optional[str]
    address: Optional[str]
    contact_person: Optional[str]
    contact: Optional[str]
    email: Optional[str]


class CropDetails(BaseModel):
    crop_id: str
    crop_type: str
    quantity_kg: float
    price: float


class PickupDetails(BaseModel):
    pickup_from: str            # warehouse / farm
    pickup_id: str
    name: Optional[str]
    location: Optional[str]
    pickup_date: Optional[str]


class FarmerOrderModel(BaseModel):
    farmer_id: str
    order_id: str
    status: str = "Created"

    order_details: List[OrderDetails]
    crop_details: List[CropDetails]
    pickup_details: List[PickupDetails]

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
