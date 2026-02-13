# backend/services/farmer/dashboard_services.py

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.models.farmer.dashboard_models import (
    DashboardData,
    KPIBlock,
    OrdersOverview,
    ShipmentsOverview,
    TaskItem,
    GeoBlock,
    CropMeta,
)

# ---------------------------------------------------------
# Mongo safe access helpers
# ---------------------------------------------------------
def _mongo_db():
    """
    Returns mongo.db if Mongo is initialized; otherwise None.
    This prevents crashes when DISABLE_MONGO=1 or MONGO_URI missing.
    """
    try:
        from backend.mongo import mongo  # lazy import
        if mongo is None:
            return None
        db = getattr(mongo, "db", None)
        return db
    except Exception:
        return None


def _get_collection(db, candidates: List[str]):
    """
    Returns first available collection object from a list of candidate names.
    """
    if db is None:
        return None
    for name in candidates:
        try:
            # Flask-PyMongo allows db[name] and db.<name>; safest:
            col = db[name]
            return col
        except Exception:
            continue
    return None


# -----------------------------
# Small helpers for mixed schemas
# -----------------------------
def _first(d: Dict[str, Any], keys: List[str], default=None):
    for k in keys:
        if k in d and d.get(k) not in (None, ""):
            return d.get(k)
    return default


def _to_iso(dt_val) -> Optional[str]:
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=timezone.utc)
        return dt_val.isoformat()
    if isinstance(dt_val, str):
        return dt_val
    return None


def _safe_lower(x) -> str:
    return str(x or "").strip().lower()


def _money_label(x) -> str:
    try:
        n = float(x)
        if n.is_integer():
            return f"₹{int(n):,}"
        return f"₹{n:,.2f}"
    except Exception:
        return str(x or "-")


def _qty_label(q, unit="kg") -> str:
    try:
        n = float(q)
        if n.is_integer():
            return f"{int(n)} {unit}"
        return f"{n} {unit}"
    except Exception:
        return f"{q} {unit}".strip()


def _date_floor_iso(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _matches_till(doc_dt: Optional[datetime], till_dt: Optional[datetime]) -> bool:
    if not till_dt:
        return True
    if not doc_dt:
        return True
    end = till_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return doc_dt <= end


def _extract_dt(doc: Dict[str, Any]) -> Optional[datetime]:
    val = _first(
        doc,
        [
            "due_at", "dueAt", "dueDate",
            "created_at", "createdAt",
            "requestedAt",
            "updated_at", "updatedAt",
        ],
    )
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    if isinstance(val, str):
        try:
            v = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None
    return None


# -----------------------------
# Status mappings
# -----------------------------
ORDER_REQUESTED = {"requested", "placed", "created", "new", "order_created"}
ORDER_IN_TRANSIT = {"in_transit", "shipped", "dispatched", "out_for_delivery"}
ORDER_COMPLETED = {"delivered", "completed", "fulfilled", "closed"}

PAYMENT_PENDING = {"pending", "due", "unpaid", "pending_payment"}
PAYMENT_RECEIVED = {"paid", "received", "success"}

SHIP_REQUESTED = {"requested", "created", "new"}
SHIP_PENDING = {"pending", "pending_pickup", "awaiting_pickup"}
SHIP_IN_TRANSIT = {"in_transit", "shipped", "dispatched"}
SHIP_DELIVERED = {"delivered", "completed"}


def to_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        v = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(v) if isinstance(val, str) else None
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


class DashboardService:
    @staticmethod
    def build_dashboard(farmer_id: str, till_date: Optional[str] = None) -> Dict[str, Any]:
        till_dt = _date_floor_iso(till_date) if till_date else None

        d = DashboardData()

        # 1) KPIs
        active_crops = DashboardService._count_active_crops(farmer_id)
        pending_payments = DashboardService._count_pending_payments(farmer_id)
        buyer_offers = DashboardService._count_buyer_offers(farmer_id)
        upcoming_shipments = DashboardService._count_upcoming_shipments(farmer_id)

        d.kpis = KPIBlock(
            active_crops=active_crops,
            pending_payments=pending_payments,
            buyer_offers=buyer_offers,
            upcoming_shipments=upcoming_shipments,
        )

        # 2) Overviews
        d.orders = DashboardService._orders_overview(farmer_id, till_dt)
        d.shipments = DashboardService._shipments_overview(farmer_id, till_dt)

        # 3) Right-side lists
        d.pending_tasks = DashboardService._pending_tasks(farmer_id, till_dt)
        d.warehouse_requests = DashboardService._farmer_requests_by_kind(farmer_id, "storage", till_dt)
        d.manufacturer_requests = DashboardService._farmer_requests_by_kind(farmer_id, "processing", till_dt)

        # 4) Crops dropdown
        d.crops = DashboardService._collect_crop_types(farmer_id) or ["Wheat"]

        # 5) Soil dummy
        d.soil = {
            "labels": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            "soil_temp": [5.6, 5.7, 5.65, 5.9, 6.0, 6.35, 5.8],
            "soil_moisture": [20, 22, 21, 23, 25, 26, 24],
            "ph": [6.1, 6.1, 6.0, 6.2, 6.2, 6.1, 6.1],
            "npk": [2, 2, 3, 3, 3, 4, 3],
        }

        # 6) Meta
        geo, crop_meta, weather_url = DashboardService._best_effort_meta(farmer_id)
        d.geo = geo
        d.crop_meta = crop_meta
        d.weather_image_url = weather_url

        return d.to_dict()

    # -----------------------------
    # KPIs
    # -----------------------------
    @staticmethod
    def _count_active_crops(farmer_id: str) -> int:
        db = _mongo_db()
        if db is None:
            return 0

        try:
            collection = db["farm_coordinates"]
            count = collection.count_documents({
                "user_id": farmer_id
            })
            return count
        except Exception as e:
            print(f"Error counting crops: {e}")
            return 0


    @staticmethod
    def _count_pending_payments(farmer_id: str) -> int:
        db = _mongo_db()
        if db is None:
            return 0

        col = _get_collection(db, ["farmer_orders"])
        if col is None:
            return 0

        query = {"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}]}
        docs = list(col.find(query, {"payment_status": 1, "paymentStatus": 1, "status": 1, "order_status": 1}))
        count = 0
        for o in docs:
            pay = _safe_lower(_first(o, ["payment_status", "paymentStatus"]))
            st = _safe_lower(_first(o, ["status", "order_status", "orderStatus"]))
            if pay in PAYMENT_PENDING or st in PAYMENT_PENDING:
                count += 1
        return count


    @staticmethod
    def _count_buyer_offers(farmer_id: str) -> int:
        db = _mongo_db()
        if db is None:
            return 0

        try:
            col = db["marketplace"]

            query = {
                "$or": [
                    {"farmer_id": farmer_id},
                    {"last_negotiation.farmer_id": farmer_id},
                    {"negotiations.farmer_id": farmer_id}
                ],
                "status": {"$in": ["Active", "Open"]}
            }

            return col.count_documents(query)

        except Exception as e:
            print(f"Error counting buyer offers: {e}")
            return 0

    @staticmethod
    def _count_upcoming_shipments(farmer_id: str) -> int:
        db = _mongo_db()
        if db is None:
            return 0

        try:
            col = db["transporter_request"]

            query = {
                "farmer_id": farmer_id,
                "status": {
                    "$in": [
                        "pending",
                        "pending_pickup",
                        "assigned",
                        "in_transit"
                    ]
                }
            }

            return col.count_documents(query)

        except Exception as e:
            print(f"Error counting shipments: {e}")
            return 0


    # -----------------------------
    # Polygons
    # -----------------------------

    @staticmethod
    def get_farm_polygons(user_id: str, crop_type: str = None, crop_id: str = None):
        db = _mongo_db()
        if db is None:
            return []

        col = db["farm_coordinates"]

        q = {"user_id": user_id}

        # ✅ Most specific filter first
        if crop_id:
            q["crop_id"] = crop_id
        elif crop_type:
            # ✅ IMPORTANT:
            # UI might send crop name (Wheat) while DB stores cropType as category (Cash Crops).
            # So match across possible fields using $or.
            q["$or"] = [
                {"cropType": crop_type},       # category (Cash Crops)
                {"crop_type": crop_type},      # if older docs
                {"cropName": crop_type},       # if you store name in some docs
                {"crop_name": crop_type},      # if older naming
            ]

        docs = list(col.find(q).sort("created_at", -1))

        out = []
        for d in docs:
            coords = d.get("coordinates", []) or []
            poly = []

            for p in coords:
                try:
                    if not isinstance(p, dict):
                        continue

                    lat_raw = p.get("lat")
                    lng_raw = p.get("lng")
                    if lng_raw is None:
                        lng_raw = p.get("long")  # ✅ handle bad key

                    if lat_raw is None or lng_raw is None:
                        continue

                    lat = float(str(lat_raw).strip())
                    lng = float(str(lng_raw).strip())

                    # ✅ Avoid InvalidValueError: finite coords check
                    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                        continue

                    poly.append({"lat": lat, "lng": lng})
                except Exception:
                    continue

            # ✅ polygon must have at least 3 points
            if len(poly) < 3:
                continue

            out.append({
                "id": str(d.get("_id")),
                "crop_id": d.get("crop_id", ""),
                "cropType": d.get("cropType", "") or d.get("crop_type", "") or d.get("cropName", "") or d.get("crop_name", ""),
                "area_size": d.get("area_size", ""),
                "date_planted": d.get("date_planted", ""),
                "created_at": d.get("created_at", ""),
                "coordinates": poly,
            })

        return out



    # -----------------------------
    # Overview blocks
    # -----------------------------
    @staticmethod
    def _orders_overview(farmer_id: str, till_dt: Optional[datetime]) -> OrdersOverview:
        db = _mongo_db()
        if db is None:
            return OrdersOverview()

        col = _get_collection(db, ["farmer_orders"])
        if col is None:
            return OrdersOverview()

        docs = list(col.find({"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}]}))

        out = OrdersOverview()
        for o in docs:
            dt = _extract_dt(o)
            if not _matches_till(dt, till_dt):
                continue

            st = _safe_lower(_first(o, ["status", "order_status", "orderStatus"]))
            pay = _safe_lower(_first(o, ["payment_status", "paymentStatus"]))

            if st in ORDER_REQUESTED:
                out.requested += 1
            elif st in ORDER_IN_TRANSIT:
                out.in_transit += 1
            elif st in ORDER_COMPLETED:
                out.completed += 1

            if pay in PAYMENT_RECEIVED:
                out.payment_received += 1

        return out

    @staticmethod
    def _shipments_overview(farmer_id: str, till_dt: Optional[datetime]) -> ShipmentsOverview:
        db = _mongo_db()
        if db is None:
            return ShipmentsOverview()

        col = db["transporter_request"]

        query = {
            "$or": [
                {"farmer_id": farmer_id},
                {"farmerId": farmer_id}
            ]
        }

        docs = list(col.find(query))

        print("Shipment docs found:", len(docs))

        out = ShipmentsOverview()

        for s in docs:

            # ---- DATE FILTER ----
            dt = s.get("created_at") or s.get("updated_at")

            if isinstance(dt, dict) and "$date" in dt:
                dt = datetime.fromisoformat(dt["$date"].replace("Z", "+00:00"))

            if till_dt and dt and dt > till_dt:
                continue

            # ---- STATUS COUNT ----
            st = str(s.get("status", "")).strip().lower()

            print("Shipment status:", st)

            if st == "requested":
                out.requested += 1
            elif st == "pending":
                out.pending += 1
            elif st in ["in transit", "in_transit"]:
                out.in_transit += 1
            elif st == "delivered":
                out.delivered += 1

            # ---- PAYMENT LOGIC ----
            payment_details = s.get("payment_details", [])
            if payment_details:
                terms = str(payment_details[0].get("payment_terms", "")).lower()
                if "delivery" in terms and st == "delivered":
                    out.payment += 1

        print("Final shipment overview:", out.__dict__)

        return out


    # -----------------------------
    # Right-side lists
    # -----------------------------
    @staticmethod
    def _pending_tasks(farmer_id: str, till_dt: Optional[datetime]) -> List[TaskItem]:
        db = _mongo_db()
        if db is None:
            return []

        tasks: List[TaskItem] = []

        farmer_orders = _get_collection(db, ["farmer_orders"])
        marketplace = _get_collection(db, ["marketplace_requests", "market_place"])
        transporter_request = _get_collection(db, ["transporter_request", "transport_request"])
        farmer_request = _get_collection(db, ["farmer_request"])

        # A) Pending payments from farmer_orders
        if farmer_orders is not None:
            for o in farmer_orders.find({"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}]}):
                dt = _extract_dt(o)
                if not _matches_till(dt, till_dt):
                    continue

                pay = _safe_lower(_first(o, ["payment_status", "paymentStatus"]))
                st = _safe_lower(_first(o, ["status", "order_status", "orderStatus"]))

                if pay in PAYMENT_PENDING or st in PAYMENT_PENDING:
                    order_id = _first(o, ["order_id", "orderId", "invoice_id", "invoiceId"], "-")
                    tasks.append(
                        TaskItem(
                            title="Payment pending",
                            sub=f"Order #{order_id}",
                            status="pending",
                            due_at=_to_iso(_first(o, ["due_at", "dueAt", "dueDate"])),
                            created_at=_to_iso(_first(o, ["created_at", "createdAt"])),
                            meta={"source": "farmer_orders"},
                        )
                    )

                if st in ORDER_REQUESTED:
                    order_id = _first(o, ["order_id", "orderId"], "-")
                    tasks.append(
                        TaskItem(
                            title="Create shipment for order",
                            sub=f"Order #{order_id}",
                            status="requested",
                            due_at=_to_iso(_first(o, ["created_at", "createdAt"])),
                            created_at=_to_iso(_first(o, ["created_at", "createdAt"])),
                            meta={"source": "farmer_orders"},
                        )
                    )

        # B) Marketplace offers
        if marketplace is not None:
            for r in marketplace.find(
                {"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}], "status": {"$nin": ["rejected"]}}
            ):
                dt = _extract_dt(r)
                if not _matches_till(dt, till_dt):
                    continue

                buyer = _first(r, ["buyer_name", "buyerName"], "Buyer")
                crop = _first(r, ["crop_name", "cropName", "cropType"], "")
                status = _first(r, ["status"], "requested")

                tasks.append(
                    TaskItem(
                        title="Buyer offer received",
                        sub=f"{buyer}" + (f" • {crop}" if crop else ""),
                        status=status,
                        due_at=_to_iso(_first(r, ["created_at", "createdAt"])),
                        created_at=_to_iso(_first(r, ["created_at", "createdAt"])),
                        meta={"source": "marketplace_requests"},
                    )
                )

        # C) Transport requests pending
        if transporter_request is not None:
            for tr in transporter_request.find(
                {"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}], "status": {"$in": ["pending", "pending_pickup", "Pending", "PENDING"]}}
            ):
                dt = _extract_dt(tr)
                if not _matches_till(dt, till_dt):
                    continue

                ship_id = _first(tr, ["crop_id", "order_id", "request_id", "requestId"], "")
                tasks.append(
                    TaskItem(
                        title="Upcoming shipment",
                        sub=f"{('Shipment #' + str(ship_id)) if ship_id else 'Transport request pending'}",
                        status="pending",
                        due_at=_to_iso(_first(tr, ["pickup_date", "pickupDate", "created_at", "createdAt"])),
                        created_at=_to_iso(_first(tr, ["created_at", "createdAt"])),
                        meta={"source": "transporter_request"},
                    )
                )

        # D) Farmer requests pending
        if farmer_request is not None:
            for fr in farmer_request.find({"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}]}):
                dt = _extract_dt(fr)
                if not _matches_till(dt, till_dt):
                    continue

                status = _safe_lower(_first(fr, ["status"], ""))
                if status in ("pending", "requested", "approval_pending", "pending_payment"):
                    kind = _safe_lower(_first(fr, ["requestKind", "request_kind"], "request"))
                    crop = _first(fr, ["crop_name", "cropName", "cropType"], "Crop")
                    entity = _first(fr, ["warehouseName", "manufacturerName", "entityName", "to_name", "toName"], "")

                    tasks.append(
                        TaskItem(
                            title=f"{kind.capitalize()} request",
                            sub=f"{crop}" + (f" • {entity}" if entity else ""),
                            status=_first(fr, ["status"], "pending"),
                            due_at=_to_iso(_first(fr, ["created_at", "createdAt", "requestedAt"])),
                            created_at=_to_iso(_first(fr, ["created_at", "createdAt"])),
                            meta={"source": "farmer_request", "requestKind": kind},
                        )
                    )

        def sort_key(t: TaskItem):
            v = to_dt(t.due_at) or to_dt(t.created_at) or datetime(1970, 1, 1, tzinfo=timezone.utc)
            return v

        tasks.sort(key=sort_key, reverse=True)
        return tasks[:40]

    @staticmethod
    def _farmer_requests_by_kind(
        farmer_id: str, kind: str, till_dt: Optional[datetime]
    ) -> List[TaskItem]:

        db = _mongo_db()
        if db is None:
            return []

        farmer_request = db["farmer_request"]

        kind = _safe_lower(kind)
        out: List[TaskItem] = []

        query = {
            "$and": [
                {
                    "$or": [
                        {"farmer_id": farmer_id},
                        {"farmerId": farmer_id},
                    ]
                },
                {
                    "$or": [
                        {"requestKind": kind},
                        {"request_kind": kind},
                        {"requestKind": kind.upper()},
                    ]
                },
            ]
        }

        docs = list(farmer_request.find(query))

        for fr in docs:
            dt = _extract_dt(fr)
            if not _matches_till(dt, till_dt):
                continue

            crop = _first(fr, ["crop_name", "cropName", "cropType"], "Wheat")
            entity = (
                _first(fr, ["warehouseName", "warehouse_name"], "")
                if kind == "storage"
                else _first(fr, ["manufacturerName", "manufacturer_name"], "")
            )
            status = _first(fr, ["status"], "requested")

            out.append(
                TaskItem(
                    title=crop,
                    sub=(entity or "—"),
                    status=status,
                    due_at=_to_iso(_first(fr, ["created_at", "createdAt", "requestedAt"])),
                    created_at=_to_iso(_first(fr, ["created_at", "createdAt"])),
                    meta={"source": "farmer_request", "requestKind": kind},
                )
            )

        out.sort(
            key=lambda x: (
                to_dt(x.due_at)
                or to_dt(x.created_at)
                or datetime(1970, 1, 1, tzinfo=timezone.utc)
            ),
            reverse=True,
        )

        return out[:40]


    # -----------------------------
    # Crop list for dropdown
    # -----------------------------
    @staticmethod
    def _collect_crop_types(farmer_id: str) -> List[str]:
        db = _mongo_db()
        if db is None:
            return []

        crops = set()

        marketplace = _get_collection(db, ["marketplace_requests", "market_place"])
        farmer_request = _get_collection(db, ["farmer_request"])
        farmer_orders = _get_collection(db, ["farmer_orders"])

        try:
            if marketplace is not None:
                for r in marketplace.find({"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}]}, {"crop_name": 1, "cropType": 1}):
                    c = _first(r, ["crop_name", "cropType"])
                    if c:
                        crops.add(str(c))
        except Exception:
            pass

        try:
            if farmer_request is not None:
                for fr in farmer_request.find({"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}]}, {"crop_name": 1, "cropType": 1}):
                    c = _first(fr, ["crop_name", "cropType"])
                    if c:
                        crops.add(str(c))
        except Exception:
            pass

        try:
            if farmer_orders is not None:
                for o in farmer_orders.find({"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}]}, {"crop_name": 1, "cropType": 1}):
                    c = _first(o, ["crop_name", "cropType"])
                    if c:
                        crops.add(str(c))
        except Exception:
            pass

        return sorted(list(crops))

    # -----------------------------
    # Optional meta (geo/crop_meta/weather url)
    # -----------------------------
    @staticmethod
    def _best_effort_meta(farmer_id: str) -> Tuple[GeoBlock, CropMeta, str]:
        geo = GeoBlock(lat="19.2046", lng="73.8745", address="")
        crop_meta = CropMeta(
            crop_id="",
            crop_name="Wheat",
            crop_type="Grain",
            grade="A",
            planting_date="",
            harvest_date="",
        )
        weather_url = ""

        db = _mongo_db()
        if db is None:
            return geo, crop_meta, weather_url

        farmer_request = _get_collection(db, ["farmer_request"])
        if farmer_request is None:
            return geo, crop_meta, weather_url

        try:
            fr = farmer_request.find_one(
                {"$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}]},
                sort=[("created_at", -1)],
            )
            if fr:
                crop_meta.crop_name = str(_first(fr, ["crop_name", "cropType"], crop_meta.crop_name) or crop_meta.crop_name)
                crop_meta.crop_id = str(_first(fr, ["crop_id", "cropId"], crop_meta.crop_id) or crop_meta.crop_id)
                geo.address = str(_first(fr, ["location", "farmLocation", "address"], geo.address) or geo.address)

                lat = _first(fr, ["lat", "latitude"])
                lng = _first(fr, ["lng", "longitude"])
                if lat:
                    geo.lat = str(lat)
                if lng:
                    geo.lng = str(lng)
        except Exception:
            pass

        return geo, crop_meta, weather_url
