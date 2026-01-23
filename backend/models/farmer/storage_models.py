# backend/models/farmer/storage_models.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# ---------------- existing models already in your file ----------------
class StorageCropModel(BaseModel):
    cropId: str
    cropName: str
    quantity: float


class StorageRequestModel(BaseModel):
    farmerId: str
    warehouseId: str
    warehouseName: str
    storageDate: str
    storageDuration: str

    paymentMode: Optional[str]
    amount: float

    crops: List[StorageCropModel] = []
    notes: Optional[str] = None


class StorageCreateModel(BaseModel):
    cropId: str
    quantity: float
    warehouseId: str
    description: str | None = None


# ==========================================================
# ✅ NEW: MODELS for WarehouseInfo page (UI payload)
# ==========================================================
class WarehouseStoredCropUIModel(BaseModel):
    cropId: str
    cropName: Optional[str] = "-"
    storedOn: Optional[str] = "-"
    quantityKg: Optional[float] = 0
    section: Optional[str] = "-"
    linkedOrder: Optional[str] = "-"
    linkedShipment: Optional[str] = "-"
    imageUrl: Optional[str] = None


class WarehouseInfoUIModel(BaseModel):
    warehouseId: str
    warehouseName: str
    officeAddress: Optional[str] = "-"
    location: Optional[str] = "-"
    owner: Optional[str] = "-"
    contact: Optional[str] = "-"
    totalCapacity: Optional[str] = "-"
    storageType: Optional[str] = "-"
    temperature: Optional[str] = "-"
    batchesActive: Optional[int] = 0

    storedCrops: List[WarehouseStoredCropUIModel] = []
    raw: Optional[Dict[str, Any]] = None
