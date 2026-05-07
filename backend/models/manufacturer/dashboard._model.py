from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

@dataclass
class KPIBlock:
    total_products: int=0
    requested_products: int =0
    active_operations: int=0
    processed_operations: int=0


@dataclass
class ProductMgmt:
    total_products: int=0
    requested_products: int =0
    active_operations: int=0
    processed_operations: int=0


@dataclass
class ProcessingOverview:
    total_products: int=0
    processing_service: int =0
    processing_stage: int=0
    processed_products: int=0



@dataclass
class PackagingOverview:
    total_products: int=0
    total_qrcode: int =0
    total_rfid: int=0
    inprocess: int=0



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
class CropMeta:
    crop_id: str = ""
    crop_name: str = ""
    crop_type: str = ""
    grade: str = ""
    received_date: str = ""
    processed_date: str = ""



@dataclass
class DashboardData:
    kpis: KPIBlock = field(default_factory=KPIBlock)
    products: List[str] = field(default_factory=lambda:["Wheat"])
    processing: ProcessingOverview = field(default_factory=ProcessingOverview)
    orders: OrdersOverview = field(default_factory=OrdersOverview)
    shipments: ShipmentsOverview = field(default_factory=ShipmentsOverview)
    pending_tasks: List[TaskItem] = field(default_factory=list)
    farmer_requests: List[TaskItem] = field(default_factory=list)
    weather_image_url: str = ""
    crop_meta: CropMeta = field(default_factory=CropMeta)
    