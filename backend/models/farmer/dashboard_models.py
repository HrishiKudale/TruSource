# backend/models/farmer/dashboard_model.py

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


@dataclass
class KPIBlock:
    active_crops: int = 0
    pending_payments: int = 0
    buyer_offers: int = 0
    upcoming_shipments: int = 0


@dataclass
class OrdersOverview:
    requested: int = 0
    in_transit: int = 0
    completed: int = 0
    payment_received: int = 0


@dataclass
class ShipmentsOverview:
    requested: int = 0
    pending: int = 0
    in_transit: int = 0
    delivered: int = 0
    payment: int = 0


@dataclass
class TaskItem:
    title: str
    sub: str = ""
    status: str = ""
    due_at: Optional[str] = None
    created_at: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeoBlock:
    lat: str = ""
    lng: str = ""
    address: str = ""


@dataclass
class CropMeta:
    crop_id: str = ""
    crop_name: str = ""
    crop_type: str = ""
    grade: str = ""
    planting_date: str = ""
    harvest_date: str = ""


@dataclass
class DashboardData:
    kpis: KPIBlock = field(default_factory=KPIBlock)
    crops: List[str] = field(default_factory=lambda: ["Wheat"])
    soil: Dict[str, Any] = field(default_factory=dict)
    orders: OrdersOverview = field(default_factory=OrdersOverview)
    shipments: ShipmentsOverview = field(default_factory=ShipmentsOverview)
    pending_tasks: List[TaskItem] = field(default_factory=list)
    warehouse_requests: List[TaskItem] = field(default_factory=list)
    manufacturer_requests: List[TaskItem] = field(default_factory=list)
    weather_image_url: str = ""
    geo: GeoBlock = field(default_factory=GeoBlock)
    crop_meta: CropMeta = field(default_factory=CropMeta)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Convert TaskItem dataclasses to dict cleanly
        d["pending_tasks"] = [asdict(x) for x in self.pending_tasks]
        d["warehouse_requests"] = [asdict(x) for x in self.warehouse_requests]
        d["manufacturer_requests"] = [asdict(x) for x in self.manufacturer_requests]
        return d
