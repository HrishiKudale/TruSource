# backend/services/farmer/orders_service.py

from datetime import datetime, timezone
from backend.mongo import mongo
from bson import ObjectId
import random


class OrderService:

    # =========================
    # ID GENERATORS
    # =========================
    @staticmethod
    def generate_order_id():
        # ORD-YYYYMMDD-XXXXX
        now = datetime.now(timezone.utc)
        date_part = now.strftime("%Y%m%d")
        suffix = random.randint(10000, 99999)
        return f"ORD-{date_part}-{suffix}"

    # (optional) if you already added generate_request_id API later
    @staticmethod
    def generate_request_id(prefix="REQ-FRM"):
        now = datetime.now(timezone.utc)
        suffix = int(now.timestamp())
        rnd = random.randint(100, 999)
        return f"{prefix}-{suffix}-{rnd}"

    # =========================
    # USER HELPERS
    # =========================
    @staticmethod
    def _find_user_by_user_id(user_id: str):
        db_users = mongo.db.users
        return (
            db_users.find_one({"user_id": user_id})
            or db_users.find_one({"userId": user_id})
            or db_users.find_one({"id": user_id})
            or db_users.find_one({"_id": ObjectId(user_id)}) if ObjectId.is_valid(user_id) else {}
        ) or {}

    @staticmethod
    def _normalize_buyer(user_doc: dict, fallback_buyer_type: str = "-"):
        return {
            "buyer_name": user_doc.get("name")
                        or user_doc.get("fullName")
                        or user_doc.get("companyName")
                        or "-",

            "buyer_type": user_doc.get("role")
                        or user_doc.get("userType")
                        or fallback_buyer_type
                        or "-",

            "office_address": user_doc.get("officeAddress")
                              or user_doc.get("address")
                              or user_doc.get("location")
                              or "-",

            "contact_person": user_doc.get("contactPerson")
                              or user_doc.get("name")
                              or user_doc.get("fullName")
                              or "-",

            "phone": user_doc.get("phone")
                     or user_doc.get("mobile")
                     or user_doc.get("contact")
                     or "-",

            "email": user_doc.get("email") or "-",
        }

    # =========================
    # READ: LIST ORDERS (NEW farmer_orders + fallback old orders)
    # =========================
    @staticmethod
    def list_orders_for_farmer(farmer_id: str):
        rows = []

        # NEW COLLECTION (preferred)
        db_new = mongo.db.farmer_orders
        new_docs = list(db_new.find({"farmer_id": farmer_id}).sort("created_at", -1))

        for d in new_docs:
            od = (d.get("order_details") or [{}])[0]
            cd = (d.get("crop_details") or [{}])[0]
            pd = (d.get("pickup_details") or [{}])[0]

            buyer_id = od.get("buyer_id") or ""
            buyer_type = od.get("buyer_type") or "-"

            # if buyer fields missing in doc, resolve from users
            buyer_name = od.get("buyer_name")
            if not buyer_name or buyer_name == "-":
                buyer_doc = OrderService._find_user_by_user_id(buyer_id)
                buyer_norm = OrderService._normalize_buyer(buyer_doc, buyer_type)
                buyer_name = buyer_norm["buyer_name"]
                buyer_type = buyer_norm["buyer_type"]

            rows.append({
                "_id": str(d.get("_id")),
                "orderId": d.get("order_id") or "-",
                "orderDate": od.get("order_date") or od.get("orderDate") or "-",
                "pickupDate": (pd.get("pickup_date") or pd.get("pickupDate") or "-"),
                "cropId": cd.get("crop_id") or "-",
                "cropType": cd.get("crop_type") or "-",
                "quantityKg": cd.get("quantity_kg") or 0,
                "price": cd.get("price") or 0,
                "buyerId": buyer_id,
                "buyerType": buyer_type,
                "buyerName": buyer_name,
                "status": d.get("status") or "Created",
            })

        # FALLBACK: OLD COLLECTION if you still have legacy docs
        if not rows:
            db_old = mongo.db.farmer_orders
            old_docs = list(db_old.find({"farmerId": farmer_id}).sort("created_at", -1))
            for d in old_docs:
                buyer_id = d.get("buyerId") or ""
                buyer_type = d.get("buyerType") or d.get("orderType") or "-"
                buyer_doc = OrderService._find_user_by_user_id(buyer_id)
                buyer_norm = OrderService._normalize_buyer(buyer_doc, buyer_type)

                rows.append({
                    "_id": str(d.get("_id")),
                    "orderId": d.get("orderId") or "-",
                    "orderDate": d.get("orderDate") or "-",
                    "pickupDate": d.get("pickupDate") or d.get("deliveryDate") or "-",
                    "cropId": d.get("cropId") or "-",
                    "cropType": d.get("cropType") or "-",
                    "quantityKg": d.get("quantityKg") or 0,
                    "price": d.get("price") or 0,
                    "buyerId": buyer_id,
                    "buyerType": buyer_type,
                    "buyerName": buyer_norm["buyer_name"],
                    "status": d.get("status") or "Created",
                })

        return rows

    # =========================
    # KPIs (based on farmer_orders; fallback old orders)
    # =========================
    @staticmethod
    def get_kpis(farmer_id: str):
        db_new = mongo.db.farmer_orders
        docs = list(db_new.find({"farmer_id": farmer_id}))

        if docs:
            total_active = sum(
                1 for d in docs
                if (d.get("status") or "").lower() in ["created", "pending", "in-transit", "active"]
            )
            total_pending = sum(
                1 for d in docs
                if (d.get("status") or "").lower() in ["pending", "created"]
            )
            total_delivered = sum(
                1 for d in docs
                if (d.get("status") or "").lower() in ["delivered", "completed"]
            )

            # price stored inside crop_details[0].price
            total_revenue = 0
            for d in docs:
                cd = (d.get("crop_details") or [{}])[0]
                total_revenue += float(cd.get("price") or 0)

            return total_active, total_pending, total_delivered, total_revenue

        # fallback old
        db_old = mongo.db.orders
        old_docs = list(db_old.find({"farmerId": farmer_id}))
        total_active = sum(1 for d in old_docs if (d.get("status") or "").lower() in ["created", "pending", "in-transit", "active"])
        total_pending = sum(1 for d in old_docs if (d.get("status") or "").lower() in ["pending", "created"])
        total_delivered = sum(1 for d in old_docs if (d.get("status") or "").lower() in ["delivered", "completed"])
        total_revenue = sum(float(d.get("price") or 0) for d in old_docs)
        return total_active, total_pending, total_delivered, total_revenue

    # =========================
    # PREFILL SOURCE: farmer_requests (unchanged)
    # =========================
    @staticmethod
    def get_farmer_request(request_id: str):
        db_req = mongo.db.farmer_requests

        doc = None
        try:
            if ObjectId.is_valid(request_id):
                doc = db_req.find_one({"_id": ObjectId(request_id)})
        except Exception:
            doc = None

        if not doc:
            doc = db_req.find_one({"requestId": request_id}) or db_req.find_one({"id": request_id})

        if not doc:
            return {"error": "Request not found"}

        return {
            "requestId": str(doc.get("_id")) if doc.get("_id") else (doc.get("requestId") or request_id),
            "buyerId": doc.get("buyerId") or doc.get("buyer_id") or "",
            "buyerType": doc.get("buyerType") or doc.get("buyer_type") or "",
            "cropId": doc.get("cropId") or doc.get("crop_id") or "",
            "cropType": doc.get("cropType") or doc.get("crop_name") or "",
            "quantityKg": doc.get("quantityKg") or doc.get("quantity") or 0,
            "pickupFrom": doc.get("pickupFrom") or doc.get("location") or "",
        }

    @staticmethod
    def get_buyer_details(buyer_id: str, buyer_type_hint: str = "-"):
        u = OrderService._find_user_by_user_id(buyer_id)
        return OrderService._normalize_buyer(u, buyer_type_hint)

    # =========================
    # CREATE ORDER -> farmer_orders (NEW schema)
    # =========================
    @staticmethod
    def create_order(payload: dict):
        db_orders = mongo.db.farmer_orders

        farmer_id = payload.get("farmerId")
        buyer_id = payload.get("buyerId")
        crop_id = payload.get("cropId") or payload.get("crop_id")
        crop_type = payload.get("cropType") or payload.get("crop_type")

        if not farmer_id or not buyer_id or not crop_id:
            return {"error": "Missing farmerId/buyerId/cropId"}

        # auto-generate if missing
        order_id = payload.get("orderId") or OrderService.generate_order_id()
        request_id = payload.get("requestId") or payload.get("request_id") or ""

        # Resolve buyer details from users (or use form values)
        buyer_doc = OrderService._find_user_by_user_id(buyer_id)
        buyer_norm = OrderService._normalize_buyer(buyer_doc, payload.get("buyerType") or "-")

        buyer_name = payload.get("buyerName") or buyer_norm["buyer_name"]
        buyer_type = payload.get("buyerType") or buyer_norm["buyer_type"]

        address = payload.get("buyerAddress") or buyer_norm["office_address"]
        contact_person = payload.get("buyerContactPerson") or buyer_norm["contact_person"]
        contact = payload.get("buyerContact") or buyer_norm["phone"]
        email = payload.get("buyerEmail") or buyer_norm["email"]

        # Dates
        order_date = payload.get("orderDate") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pickup_date = payload.get("pickupDate") or ""

        # Crop details
        qty = float(payload.get("quantityKg") or 0)
        price = float(payload.get("price") or 0)

        # Pickup details (supports your form naming)
        pickup_from = payload.get("pickupFromType") or payload.get("pickupFrom") or ""
        pickup_id = payload.get("pickupLocationId") or payload.get("pickupFarmId") or ""
        pickup_label = payload.get("pickupFromLabel") or ""  # you set this in JS
        pickup_location = payload.get("pickupLocation") or payload.get("pickupFrom") or ""

        now = datetime.now(timezone.utc)

        doc = {
            "farmer_id": farmer_id,
            "order_id": order_id,
            "status": payload.get("status", "Created"),

            "created_at": now,
            "updated_at": now,

            "order_details": [{
                "request_id": request_id,
                "payment_terms": payload.get("payment_terms") or payload.get("paymentTerms") or "",
                "buyer_type": buyer_type,
                "buyer_id": buyer_id,
                "buyer_name": buyer_name,
                "address": address,
                "contact_person": contact_person,
                "contact": contact,
                "email": email,
                "order_date": order_date,
            }],

            "crop_details": [{
                "crop_id": crop_id,
                "crop_type": crop_type or "",
                "quantity_kg": qty,
                "price": price,
            }],

            "pickup_details": [{
                "pickup_from": pickup_from,        # warehouse / farm
                "pickup_id": pickup_id,
                "name": pickup_label,
                "location": pickup_location,
                "pickup_date": pickup_date,
            }],
        }

        inserted = db_orders.insert_one(doc)

        return {
            "success": True,
            "order_db_id": str(inserted.inserted_id),
            "orderId": order_id
        }
    @staticmethod
    def get_order_for_farmer(farmer_id: str, order_id: str):
        """
        Fetch ONE order for this farmer from NEW schema (farmer_orders).
        Optionally falls back to old schema (orders).
        Returns a FLATTENED dict that OrderInfo.html can render easily.
        """

        # ----------------------------
        # 1) NEW schema: farmer_orders
        # ----------------------------
        fo = mongo.db.farmer_orders.find_one(
            {"farmer_id": farmer_id, "order_id": order_id},
            {"_id": 0}
        )

        if fo:
            od = (fo.get("order_details") or [{}])[0]
            cd = (fo.get("crop_details") or [{}])[0]
            pd = (fo.get("pickup_details") or [{}])[0]

            return {
                "orderId": fo.get("order_id", "-"),
                "status": fo.get("status", "Created"),
                "createdAt": (fo.get("created_at").strftime("%Y-%m-%d") if fo.get("created_at") else "-"),

                # order_details
                "requestId": od.get("request_id", "-"),
                "paymentTerms": od.get("payment_terms", "-"),
                "buyerType": od.get("buyer_type", "-"),
                "buyerId": od.get("buyer_id", "-"),
                "buyerName": od.get("buyer_name", "-"),
                "address": od.get("address", "-"),
                "contactPerson": od.get("contact_person", "-"),
                "contact": od.get("contact", "-"),
                "email": od.get("email", "-"),
                "orderDate": od.get("order_date", "-"),

                # crop_details
                "cropId": cd.get("crop_id", "-"),
                "cropType": cd.get("crop_type", "-"),
                "quantityKg": cd.get("quantity_kg", 0),
                "price": cd.get("price", 0),

                # pickup_details
                "pickupFrom": pd.get("pickup_from", "-"),
                "pickupId": pd.get("pickup_id", "-"),
                "pickupName": pd.get("name", "-"),
                "pickupLocation": pd.get("location", "-"),
                "pickupDate": pd.get("pickup_date", "-"),
            }

        # ----------------------------
        # 2) OLD schema fallback: orders
        # ----------------------------
        d = mongo.db.orders.find_one(
            {"farmerId": farmer_id, "orderId": order_id},
            {"_id": 0}
        )
        if not d:
            return None

        buyer_id = d.get("buyerId") or ""
        buyer_type = d.get("buyerType") or d.get("orderType") or "-"
        buyer_doc = OrderService._find_user_by_user_id(buyer_id)
        buyer_norm = OrderService._normalize_buyer(buyer_doc, buyer_type)

        return {
            "orderId": d.get("orderId", "-"),
            "status": d.get("status") or "Created",
            "createdAt": (d.get("created_at").strftime("%Y-%m-%d") if d.get("created_at") else "-"),

            "requestId": d.get("requestId") or "-",
            "paymentTerms": d.get("payment_terms") or "-",
            "buyerType": d.get("buyerType") or "-",
            "buyerId": d.get("buyerId") or "-",
            "buyerName": buyer_norm.get("buyer_name", "-"),
            "address": buyer_norm.get("office_address", "-"),
            "contactPerson": buyer_norm.get("contact_person", "-"),
            "contact": buyer_norm.get("phone", "-"),
            "email": buyer_norm.get("email", "-"),
            "orderDate": d.get("orderDate") or "-",

            "cropId": d.get("cropId") or "-",
            "cropType": d.get("cropType") or "-",
            "quantityKg": d.get("quantityKg") or 0,
            "price": d.get("price") or 0,

            "pickupFrom": d.get("pickupFrom") or "-",
            "pickupId": d.get("pickupLocationId") or "-",
            "pickupName": "-",
            "pickupLocation": "-",
            "pickupDate": d.get("pickupDate") or "-",
        }
