# backend/models/logistics_models.py

from pydantic import BaseModel, Field
from typing import Optional, List


# -----------------------------
# 1) SHIPMENT DETAILS ARRAY
# -----------------------------
class ShipmentDetails(BaseModel):
    pickup_from: str = ""
    pickup_id: str = ""
    pickup_name: str = ""
    pickup_location: str = ""

    deliver_to: str = ""
    deliver_id: str = ""
    deliver_name: str = ""
    deliver_location: str = ""


# -----------------------------
# 2) TRANSPORTER DETAILS ARRAY
# -----------------------------
class TransporterDetails(BaseModel):
    transporter_mode: str = "platform"
    transporter_name: str = ""
    transporter_id: str = ""
    personal_transporter_name: str = ""
    vehicle_type: str = ""
    pickup_date: str = ""
    delivery_date: str = ""


# -----------------------------
# 3) PAYMENT DETAILS ARRAY
# -----------------------------
class PaymentDetails(BaseModel):
    payment_terms: str = ""
    insurance_requested: bool = False
    declared_value: str = ""
    coverage_note: str = ""
    transporter_note: str = ""


# -----------------------------
# 4) SHIPMENT ITEMS ARRAY
# -----------------------------
class ShipmentItem(BaseModel):
    order_id: str = ""
    order_date: str = ""
    crop_id: str = ""
    crop_name: str = ""
    quantity: str = ""


# -----------------------------
# FULL REQUEST MODEL
# -----------------------------
class TransporterRequestModel(BaseModel):
    farmer_id: str = Field(..., min_length=1)

    shipment_details: List[ShipmentDetails]
    transporter_details: List[TransporterDetails]
    payment_details: List[PaymentDetails]
    shipment_items: List[ShipmentItem]

    class Config:
        extra = "allow"
 