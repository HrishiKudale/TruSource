# backend/services/farmer/storage_service.py

from datetime import datetime, timezone
import random
from typing import Dict, Any, List

from bson import ObjectId
from backend.mongo import mongo


# backend/services/farmer/storage_service.py

from datetime import datetime
from typing import Any, Dict, List
from backend.mongo import mongo


class FarmerStorageService:

    @staticmethod
    def list_storage(farmer_id: str) -> List[Dict[str, Any]]:

        cur = mongo.db.farmer_request.find(
            {
                "requestKind": "storage",
                "$or": [
                    {"farmerId": farmer_id},     # legacy
                    {"farmer_id": farmer_id},    # new
                ]
            }
        ).sort([("created_at", -1)])

        items: List[Dict[str, Any]] = []

        for d in cur:
            d["_id"] = str(d["_id"])

            # -----------------------------
            # WAREHOUSE (nested-safe)
            # -----------------------------
            wh = {}
            if isinstance(d.get("warehouse_detail"), list) and d["warehouse_detail"]:
                wh = d["warehouse_detail"][0]

            d["warehouseId"] = (
                d.get("warehouseId")
                or wh.get("warehouse_id")
                or "-"
            )

            d["warehouseName"] = (
                d.get("warehouseName")
                or wh.get("warehouse_name")
                or "-"
            )

            d["location"] = d.get("location") or "-"

            # -----------------------------
            # CROP (nested-safe)
            # -----------------------------
            cd = {}
            if isinstance(d.get("crop_detail"), list) and d["crop_detail"]:
                cd = d["crop_detail"][0]

            d["cropName"] = (
                d.get("cropName")
                or cd.get("crop_name")
                or "-"
            )

            d["harvestQuantity"] = (
                d.get("harvestQuantity")
                or cd.get("quantity")
                or 0
            )

            # -----------------------------
            # STORAGE META
            # -----------------------------
            d["storageDuration"] = (
                d.get("storageDuration")
                or wh.get("storage_duration")
                or "-"
            )

            d["status"] = d.get("status", "pending")

            upd = d.get("updated_at") or d.get("created_at")
            d["lastUpdated"] = upd.strftime("%Y-%m-%d") if upd else "-"

            items.append(d)

        return items


    @staticmethod
    def get_kpis(farmer_id: str) -> Dict[str, Any]:
        items = FarmerStorageService.list_storage(farmer_id)

        total_requests = len(items)
        unique_warehouses = len(set([i.get("warehouseId") for i in items if i.get("warehouseId") and i.get("warehouseId") != "-"]))

        total_qty = 0.0
        for i in items:
            try:
                total_qty += float(i.get("harvestQuantity") or 0)
            except Exception:
                pass

        # you can map these later if needed
        return {
            "total_warehouses": unique_warehouses,
            "total_capacity": 0,          # not available from request docs
            "shipments_linked": 0,        # not available from request docs
            "total_stored": total_qty,    # sum quantity
            "total_requests": total_requests
        }


    # -----------------------------
    # Helpers
    # -----------------------------
    @staticmethod
    def _generate_request_id():
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand = random.randint(10000, 99999)
        return f"REQ-FRM-{date_part}-{rand}"


    # -----------------------------
    # CREATE STORAGE REQUEST
    # -----------------------------
    @staticmethod
    def create_storage_requests(farmer_id: str, form) -> Dict[str, Any]:

        now = datetime.now(timezone.utc)

        # ---------- Warehouse ----------
        warehouse_id = (form.get("warehouse_id") or "").strip()
        warehouse_name = (form.get("warehouse_name") or "").strip()

        if not warehouse_id:
            return {"ok": False, "error": "Warehouse is required"}

        storage_date = form.get("date") or ""
        storage_duration = form.get("storage_duration") or ""
        payment_mode = form.get("payment_mode") or ""
        notes = form.get("note") or ""

        # ---------- Crop ----------
        crop_id = (form.get("crop_id") or "").strip()
        crop_name = (form.get("crop_name") or "").strip()

        try:
            quantity = float(form.get("quantity") or 0)
        except ValueError:
            quantity = 0

        packaging_type = form.get("packaging_type") or ""
        bagqty = form.get("bags") or ""
        moisture = form.get("moisture") or ""

        if not crop_id or quantity <= 0:
            return {"ok": False, "error": "Crop and quantity are required"}

        # ---------- Structured Document ----------
        doc = {
            "farmer_id": farmer_id,
            "request_id": FarmerStorageService._generate_request_id(),

            "requestKind": "storage",
            "status": "pending",

            "created_at": now,
            "updated_at": now,

            "warehouse_detail": [{
                "warehouse_id": warehouse_id,
                "warehouse_name": warehouse_name,
                "date": storage_date,
                "storage_duration": storage_duration,
                "payment_mode": payment_mode,
            }],

            "crop_detail": [{
                "crop_id": crop_id,
                "crop_name": crop_name,
                "quantity": quantity,
                "packaging_type": packaging_type,
                "bagqty": bagqty,
                "moisture": moisture,
            }],

            "notes": notes,
        }

        mongo.db.farmer_request.insert_one(doc)

        return {
            "ok": True,
            "request_id": doc["request_id"]
        }

    @staticmethod
    def _find_storage_request_for_farmer(farmer_id: str, request_id: str) -> Dict[str, Any] | None:
        """
        Storage request doc is in farmer_request.
        request_id is usually Mongo _id string.
        """
        base = {"farmerId": farmer_id, "requestKind": "storage"}

        # primary: by _id
        if ObjectId.is_valid(request_id):
            doc = mongo.db.farmer_request.find_one({**base, "_id": ObjectId(request_id)})
            if doc:
                return doc

        # fallback: if you store requestId as a string later
        return mongo.db.farmer_request.find_one({**base, "requestId": request_id})

    @staticmethod
    def _find_warehouse_user(warehouse_id: str) -> Dict[str, Any] | None:
        """
        Warehouse details live in users collection.
        Your sample:
          users.userId = "WRHF3E..."
        """
        u = mongo.db.users.find_one({"userId": warehouse_id})
        if not u:
            u = mongo.db.users.find_one({"warehouseId": warehouse_id})
        return u

    @staticmethod
    def _flatten_inventory_docs(inv_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize warehouse_inventory possibilities:
        A) One doc per crop
        B) One doc per warehouse with crops[] list
        """
        out: List[Dict[str, Any]] = []
        for d in inv_docs:
            if isinstance(d.get("crops"), list):
                out.extend(d["crops"])
            else:
                out.append(d)
        return out

    @staticmethod
    def _get_inventory_for_warehouse(warehouse_id: str, farmer_id: str | None = None) -> List[Dict[str, Any]]:
        """
        Get stored crop records from warehouse_inventory.
        If farmer_id provided -> only this farmer’s stored crops.
        """
        q = {"warehouseId": warehouse_id}
        if farmer_id:
            # if your inventory stores farmerId, this filters correctly
            q = {"warehouseId": warehouse_id, "farmerId": farmer_id}

        inv_docs = list(
            mongo.db.warehouse_inventory.find(q).sort([("storedOn", -1), ("created_at", -1)])
        )
        return FarmerStorageService._flatten_inventory_docs(inv_docs)

    @staticmethod
    def _normalize_inventory_crop(c: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert inventory record into UI-friendly keys.
        """
        return {
            "cropId": c.get("cropId") or c.get("crop_id") or "-",
            "cropName": c.get("cropName") or c.get("crop_name") or "-",
            "storedOn": c.get("storedOn") or c.get("stored_on") or c.get("date") or "-",
            "quantityKg": c.get("quantityKg") or c.get("quantity_kg") or c.get("quantity") or 0,
            "section": c.get("section") or c.get("block") or c.get("slot") or "-",
            "linkedOrder": c.get("linkedOrder") or c.get("orderId") or c.get("order_id") or "-",
            "linkedShipment": c.get("linkedShipment") or c.get("shipmentId") or c.get("shipment_id") or "-",
            "imageUrl": c.get("imageUrl") or c.get("image_url") or None,
        }

    @staticmethod
    def get_warehouse_info_page_data(farmer_id: str, warehouse_id: str) -> Dict[str, Any]:
        """
        Open WarehouseInfo using:
        - farmer_id (from session)
        - warehouse_id (from URL)
        Fetches:
        1) Warehouse details from users
        2) Farmer-specific stored crops from warehouse_inventory
        """

        if not warehouse_id:
            return {"ok": False, "error": "warehouse_id is required."}

        # 1) Warehouse user
        u = FarmerStorageService._find_warehouse_user(warehouse_id)
        if not u:
            return {"ok": False, "error": "Warehouse not found in users collection."}

        ss0 = {}
        if isinstance(u.get("storage_services"), list) and len(u["storage_services"]) > 0:
            ss0 = u["storage_services"][0] or {}

        # 2) inventory filtered by farmer + warehouse
        inv = FarmerStorageService._get_inventory_for_warehouse(warehouse_id, farmer_id=farmer_id)
        crops = [FarmerStorageService._normalize_inventory_crop(x) for x in inv]
        batches_active = len(crops)

        warehouse = {
            "warehouseId": u.get("userId") or warehouse_id,
            "warehouseName": u.get("officeName") or u.get("name") or "-",
            "officeAddress": u.get("officeAddress") or u.get("address") or "-",
            "location": u.get("location") or "-",

            "owner": u.get("officeName") or u.get("name") or "-",
            "contact": f"{u.get('name','-')} (+91 {u.get('phone','-')})",

            "totalCapacity": ss0.get("storage_capacity") or "-",
            "storageType": ss0.get("storage_type") or "-",
            "temperature": ss0.get("storage_temprature") or "-",
            "batchesActive": batches_active,
        }

        return {
            "ok": True,
            "warehouse_id": warehouse.get("warehouseId") or warehouse_id,
            "warehouse": warehouse,
            "crops": crops,
        }

