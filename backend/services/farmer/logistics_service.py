# backend/services/farmer/logistics_service.py

from datetime import datetime
from bson import ObjectId

from backend.mongo import mongo
from backend.blockchain import contract

# ✅ Import your Pydantic model
from backend.models.farmer.logistics_models import TransporterRequestModel


class FarmerLogisticsService:

    # ---------------------------------------------------------
    # LIST SHIPMENTS (created by farmer)
    # ---------------------------------------------------------
    @staticmethod
    def get_shipments(farmer_id: str):
        db = mongo.db.transporter_request  # ✅ single collection

        shipments = list(db.find({"farmer_id": farmer_id}).sort("created_at", -1))
        for s in shipments:
            s["_id"] = str(s["_id"])

        return {"shipments": shipments}

    # ---------------------------------------------------------
    # SINGLE SHIPMENT DETAILS
    # ---------------------------------------------------------
    @staticmethod
    def get_single_shipment(farmer_id: str, shipment_id: str):
        db = mongo.db.transporter_request

        try:
            oid = ObjectId(shipment_id)
        except Exception:
            return {"error": "Invalid shipment id"}

        shipment = db.find_one({"_id": oid, "farmer_id": farmer_id})
        if not shipment:
            return {"error": "Shipment not found"}

        shipment["_id"] = str(shipment["_id"])
        return shipment

    # ---------------------------------------------------------
    # CREATE NEW TRANSPORTER REQUEST (FULL PAYLOAD)
    # ---------------------------------------------------------
    @staticmethod
    def create_transporter_request(payload: dict):
        """
        Validates FULL payload using TransporterRequestModel (Pydantic),
        then saves to Mongo: transporter_request
        """

        # ----------------------------
        # Normalize incoming payload
        # ----------------------------
        payload = payload or {}

        # Normalize boolean (HTML form sometimes sends "on"/"true"/"1")
        # Your route already does this for HTML form, but JSON may vary.
        try:
            pd0 = (payload.get("payment_details") or [{}])[0]
            raw_ins = pd0.get("insurance_requested", False)
            if isinstance(raw_ins, str):
                pd0["insurance_requested"] = raw_ins.strip().lower() in ("1", "true", "yes", "on")
            payload["payment_details"] = [pd0]
        except Exception:
            pass

        # ----------------------------
        # Validate with Pydantic
        # ----------------------------
        try:
            model = TransporterRequestModel(**payload)
        except Exception as e:
            # Pydantic v2 error prints well; keep message readable
            return {"error": f"Payload validation failed: {str(e)}"}

        # Clean dict to insert (ensures correct keys, types)
        clean = model.model_dump()  # pydantic v2
        # If you're on pydantic v1, replace with: clean = model.dict()

        farmer_id = clean.get("farmer_id")

        # Extra guard: at least 1 shipment item
        if not clean.get("shipment_items"):
            return {"error": "Please add at least one shipment item"}

        # Extra guard: pickup/deliver required
        first = (clean.get("shipment_details") or [{}])[0]
        if not (first.get("pickup_from") and first.get("deliver_to")):
            return {"error": "Pickup from and Deliver to are required"}

        # ----------------------------
        # Insert into Mongo
        # ----------------------------
        db = mongo.db.transporter_request

        doc = {
            **clean,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        inserted = db.insert_one(doc)


        return {"ok": True, "request_id": str(inserted.inserted_id)}


    # ---------------------------------------------------------
    # DATA FOR ADD SHIPMENT MODAL (ORDERS + CROPS)
    # ---------------------------------------------------------
    @staticmethod
    def get_shipment_modal_data(farmer_id: str):
        db_orders = mongo.db.farmer_orders
        db_crops = mongo.db.farmer_request

        orders = list(db_orders.find({"farmerId": farmer_id}))
        for o in orders:
            o["_id"] = str(o["_id"])

        crops = list(db_crops.find({"farmerId": farmer_id}))
        for c in crops:
            c["_id"] = str(c["_id"])

        return {"orders": orders, "crops": crops}

    # ---------------------------------------------------------
    # USERS → PICKUP/DELIVERY ENTITIES
    # ---------------------------------------------------------
    @staticmethod
    def get_shipment_entities_from_users():
        db_users = mongo.db.users
        roles = ["farmer", "manufacturer", "warehouse", "retailer"]

        users = list(db_users.find({"role": {"$in": roles}}))

        entities = []
        for u in users:
            entity_id = (
                u.get("user_id")
                or u.get("userId")
                or u.get("farmerId")
                or u.get("manufacturerId")
                or u.get("warehouseId")
                or u.get("retailerId")
                or str(u.get("_id"))
            )

            name = u.get("name") or u.get("fullName") or u.get("officeName") or "-"
            location = u.get("location") or u.get("officeAddress") or u.get("city") or ""

            entities.append({
                "role": u.get("role", ""),
                "name": name,
                "entityId": entity_id,
                "location": location,
            })

        entities.sort(key=lambda x: (x.get("role", ""), x.get("name", "")))
        return entities

    # ---------------------------------------------------------
    # USERS → TRANSPORTERS (for transporter dropdown)
    # ---------------------------------------------------------
    @staticmethod
    def get_transport_details_from_users():
        db_users = mongo.db.users
        roles = ["transporter"]

        users = list(db_users.find({"role": {"$in": roles}}))

        entities = []
        for u in users:
            entity_id = (
                u.get("user_id")
                or u.get("userId")
                or u.get("transporterId")
                or str(u.get("_id"))
            )

            name = u.get("name") or u.get("fullName") or u.get("officeName") or "-"
            location = u.get("location") or u.get("officeAddress") or u.get("city") or ""

            entities.append({
                "role": u.get("role", ""),
                "name": name,
                "entityId": entity_id,
                "location": location,
            })

        entities.sort(key=lambda x: (x.get("name", "")))
        return entities


    # =========================================================
    # SHIPMENT INFO PAGE HELPERS
    # =========================================================

    @staticmethod
    def _to_object_id(value: str):
        try:
            return ObjectId(value)
        except Exception:
            return None

    @staticmethod
    def _safe_first(arr):
        return arr[0] if isinstance(arr, list) and len(arr) > 0 else {}

    # ---------------------------------------------------------
    # Fetch transporter_request by _id + farmer_id
    # ---------------------------------------------------------
    @staticmethod
    def get_transporter_request_by_id(farmer_id: str, request_id: str):
        db = mongo.db.transporter_request
        oid = FarmerLogisticsService._to_object_id(request_id)
        if not oid:
            return None

        doc = db.find_one({"_id": oid, "farmer_id": farmer_id})
        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        return doc

    # ---------------------------------------------------------
    # Fetch transporter_charges (best-effort linking)
    # ---------------------------------------------------------
    @staticmethod
    def get_transporter_charges_for_request(request_id: str, transporter_id: str = ""):
        """
        transporter_charges schemas differ.
        This tries multiple common keys so it doesn't break.
        """
        db = mongo.db.transporter_charges
        oid = FarmerLogisticsService._to_object_id(request_id)

        queries = [
            {"request_id": request_id},
            {"shipment_request_id": request_id},
            {"transporter_request_id": request_id},
            {"transporterRequestId": request_id},
        ]

        if oid:
            queries += [
                {"request_id": oid},
                {"shipment_request_id": oid},
                {"transporter_request_id": oid},
                {"transporterRequestId": oid},
            ]

        if transporter_id:
            queries += [
                {"transporter_id": transporter_id, "request_id": request_id},
                {"transporterId": transporter_id, "request_id": request_id},
            ]
            if oid:
                queries += [
                    {"transporter_id": transporter_id, "request_id": oid},
                    {"transporterId": transporter_id, "request_id": oid},
                ]

        found = None
        for q in queries:
            found = db.find_one(q)
            if found:
                break

        if not found:
            return None

        found["_id"] = str(found["_id"])

        # normalize to stable keys for template
        return {
            "_id": found.get("_id"),
            "transporter_name": found.get("transporter_name") or found.get("transporterName"),
            "driver_name": found.get("driver_name") or found.get("driverName"),
            "vehicle_no": found.get("vehicle_no") or found.get("vehicleNo") or found.get("vehicle_number"),
            "vehicle_type": found.get("vehicle_type") or found.get("vehicleType"),
            "driver_phone": found.get("driver_phone") or found.get("driverPhone"),
            "raw": found,
        }

    # ---------------------------------------------------------
    # Fetch user info for Deliver side (buyer type + address)
    # ---------------------------------------------------------
    @staticmethod
    def get_user_display_by_any_id(user_id: str):
        if not user_id:
            return None

        db = mongo.db.users

        user = (
            db.find_one({"user_id": user_id})
            or db.find_one({"userId": user_id})
            or db.find_one({"farmerId": user_id})
            or db.find_one({"manufacturerId": user_id})
            or db.find_one({"warehouseId": user_id})
            or db.find_one({"retailerId": user_id})
        )

        if not user:
            return None

        return {
            "name": user.get("name") or user.get("fullName") or user.get("officeName"),
            "role": user.get("role") or user.get("userRole"),
            "address": user.get("officeAddress") or user.get("location") or user.get("address") or user.get("city"),
            "raw": user,
        }

    # ---------------------------------------------------------
    # ✅ MAIN builder for ShipmentInfo.html
    # ---------------------------------------------------------
    @staticmethod
    def get_shipment_info_page_data(farmer_id: str, request_id: str):
        req = FarmerLogisticsService.get_transporter_request_by_id(farmer_id, request_id)
        if not req:
            return {"error": "Shipment request not found"}

        sd = FarmerLogisticsService._safe_first(req.get("shipment_details"))
        td = FarmerLogisticsService._safe_first(req.get("transporter_details"))
        pd = FarmerLogisticsService._safe_first(req.get("payment_details"))
        items = req.get("shipment_items") or []

        # transporter charges
        charges = FarmerLogisticsService.get_transporter_charges_for_request(
            request_id=req.get("_id"),
            transporter_id=td.get("transporter_id", "")
        )

        # deliver user display
        deliver_display = FarmerLogisticsService.get_user_display_by_any_id(sd.get("deliver_id", ""))

        return {
            "request": req,
            "shipment_details": sd,
            "transporter_details": td,
            "payment_details": pd,
            "items": items,
            "charges": charges,
            "deliver_display": deliver_display,
        }
