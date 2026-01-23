# backend/models/pricing_models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class PricingRowBase(BaseModel):
    buyerId: str = Field(..., min_length=1)
    name: str = ""
    location: str = ""


class WarehousePricingRow(PricingRowBase):
    kind: Literal["warehouse"] = "warehouse"
    storageType: str = ""
    rateLabel: str = ""


class ManufacturerPricingRow(PricingRowBase):
    kind: Literal["manufacturer"] = "manufacturer"
    cropSummary: str = ""
    processingSummary: str = ""
    rateSummary: str = ""
    tatSummary: str = ""


class TransporterPricingRow(PricingRowBase):
    kind: Literal["transporter"] = "transporter"
    coverage: str = ""
    tracking: str = ""


class PricingTables(BaseModel):
    warehouse: List[WarehousePricingRow] = []
    manufacturer: List[ManufacturerPricingRow] = []
    transporter: List[TransporterPricingRow] = []


class PricingFilters(BaseModel):
    processing_types: List[str] = []
