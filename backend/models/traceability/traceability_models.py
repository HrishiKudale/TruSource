# backend/models/traceability/traceability_models.py
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


@dataclass
class OriginHarvestBlock:
    location: str = ""
    cropName: str = ""      # ✅ UI label "Crop: Wheat"
    cropType: str = ""      # ✅ category if you want
    plantedOn: str = ""
    harvestDate: str = ""
    farmingType: str = ""
    farmerName: str = ""


@dataclass
class StorageBlock:
    # Mongo-based (optional)
    warehouseName: str = ""
    city: str = ""
    storedOn: str = ""
    qualityCheck: str = ""  # e.g. "Passed"


@dataclass
class ProcessingBlock:
    processorName: str = ""     # manufacturer name
    process: str = ""           # e.g. "Cleaning & Milling" (mongo or default)
    inputQty: str = ""          # "300 kg"
    outputQty: str = ""         # "285 kg"
    processingDate: str = ""


@dataclass
class ShipmentItem:
    title: str = ""             # "Shipment 1"
    transporter: str = ""
    deliveredTo: str = ""       # "Warehouse" / "Manufacturer" / "Distributor"
    route: str = ""             # "Nashik → Mumbai"
    date: str = ""              # optional


@dataclass
class ShipmentBlock:
    shipments: List[ShipmentItem] = field(default_factory=list)


@dataclass
class SaleBlock:
    buyerName: str = ""         # retailer/buyer
    city: str = ""
    purchaseDate: str = ""


@dataclass
class TraceabilityViewModel:
    cropId: str = ""
    originHarvest: OriginHarvestBlock = field(default_factory=OriginHarvestBlock)
    storage: Optional[StorageBlock] = None
    processing: Optional[ProcessingBlock] = None
    shipment: Optional[ShipmentBlock] = None
    sale: Optional[SaleBlock] = None

    # raw debug (optional)
    debug: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
