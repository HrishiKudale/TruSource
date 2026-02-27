# backend/services/farmer/storage_service.py

from __future__ import annotations

from datetime import datetime, timezone
import random
from typing import Dict, Any, List, Optional

from bson import ObjectId
from backend.mongo_safe import get_col


class FarmerStorageService:

    # -----------------------------
    # LIST STORAGE REQUESTS
    # -----------------------------
    @staticmethod
    def list_storage(farmer_id: str) -> List[Dict[str, Any]]:
        col = get_col("farmer_request")
        if col is None:
            print("⚠️ Mongo disabled/unavailable: list_storage returning empty")
            return []

        cur = col.find(
            {
                "requestKind": "storage",
                "$or": [
                    {"farmerId": farmer_id},     # legacy
                    {"farmer_id": farmer_id},    # new
                ],
            }
        ).sort([("created_at", -1), ("_id", -1)])

        items: List[Dict[str, Any]] = []

        for d in cur:
            d["_id"] = str(d.get("_id"))

            # -----------------------------
            # WAREHOUSE (nested-safe)
            # -----------------------------
            wh = {}
            if isinstance(d.get("warehouse_detail"), list) and d["warehouse_detail"]:
                wh = d["warehouse_detail"][0] or {}

            d["warehouseId"] = d.get("warehouseId") or wh.get("warehouse_id") or "-"
            d["warehouseName"] = d.get("warehouseName") or wh.get("warehouse_name") or "-"
            d["location"] = d.get("location") or wh.get("location") or "-"

            # -----------------------------
            # CROP (nested-safe)
            # -----------------------------
            cd = {}
            if isinstance(d.get("crop_detail"), list) and d["crop_detail"]:
                cd = d["crop_detail"][0] or {}

            d["cropName"] = d.get("cropName") or cd.get("crop_name") or "-"
            d["harvestQuantity"] = d.get("harvestQuantity") or cd.get("quantity") or 0

            # -----------------------------
            # STORAGE META
            # -----------------------------
            d["storageDuration"] = d.get("storageDuration") or wh.get("storage_duration") or "-"
            d["status"] = d.get("status", "pending")

            upd = d.get("updated_at") or d.get("created_at")
            try:
                d["lastUpdated"] = upd.strftime("%Y-%m-%d") if upd else "-"
            except Exception:
                d["lastUpdated"] = "-"

            items.append(d)

        return items

    # -----------------------------
    # KPIs
    # -----------------------------
    @staticmethod
    def get_kpis(farmer_id: str) -> Dict[str, Any]:
        items = FarmerStorageService.list_storage(farmer_id)

        total_requests = len(items)
        unique_warehouses = len(set([
            i.get("warehouseId")
            for i in items
            if i.get("warehouseId") and i.get("warehouseId") != "-"
        ]))

        total_qty = 0.0
        for i in items:
            try:
                total_qty += float(i.get("harvestQuantity") or 0)
            except Exception:
                pass

        return {
            "total_warehouses": unique_warehouses,
            "total_capacity": 0,
            "shipments_linked": 0,
            "total_stored": total_qty,
            "total_requests": total_requests
        }

    # -----------------------------
    # Helpers
    # -----------------------------
    @staticmethod
    def _generate_request_id() -> str:
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand = random.randint(10000, 99999)
        return f"REQ-FRM-{date_part}-{rand}"

    # -----------------------------
    # CREATE STORAGE REQUEST
    # -----------------------------
    @staticmethod
    def create_storage_requests(farmer_id: str, form) -> Dict[str, Any]:
        col = get_col("farmer_request")
        if col is None:
            return {"ok": False, "error": "Mongo is disabled/unavailable. Cannot create storage request."}

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

        # ---------- Crop (Single or Multiple Support) ----------
        crop_details = []

        # Try multiple-crop submission first (from table)
        items_crop_ids = form.getlist("items_crop_id[]")
        items_crop_names = form.getlist("items_crop_name[]")
        items_quantities = form.getlist("items_quantity[]")
        items_packaging = form.getlist("items_packaging_type[]")
        items_bags = form.getlist("items_bags[]")
        items_moisture = form.getlist("items_moisture[]")

        if items_crop_ids:
            # MULTIPLE CROPS MODE
            for i in range(len(items_crop_ids)):
                crop_id = (items_crop_ids[i] or "").strip()
                crop_name = (items_crop_names[i] or "").strip()

                try:
                    quantity = float(items_quantities[i] or 0)
                except (ValueError, IndexError):
                    quantity = 0

                packaging_type = items_packaging[i] if i < len(items_packaging) else ""
                bagqty = items_bags[i] if i < len(items_bags) else ""
                moisture = items_moisture[i] if i < len(items_moisture) else ""

                if not crop_id or quantity <= 0:
                    return {"ok": False, "error": "Each crop must have valid quantity"}

                crop_details.append({
                    "crop_id": crop_id,
                    "crop_name": crop_name,
                    "quantity": quantity,
                    "packaging_type": packaging_type,
                    "bagqty": bagqty,
                    "moisture": moisture,
                })

        else:
            # SINGLE CROP FALLBACK MODE
            crop_id = (form.get("crop_id") or "").strip()
            crop_name = (form.get("crop_name") or form.get("crop") or "").strip()

            try:
                quantity = float(form.get("quantity") or 0)
            except ValueError:
                quantity = 0

            packaging_type = form.get("packaging_type") or ""
            bagqty = form.get("bags") or ""
            moisture = form.get("moisture") or ""

            if not crop_id or quantity <= 0:
                return {"ok": False, "error": "Crop and quantity are required"}

            crop_details.append({
                "crop_id": crop_id,
                "crop_name": crop_name,
                "quantity": quantity,
                "packaging_type": packaging_type,
                "bagqty": bagqty,
                "moisture": moisture,
            })

        # ---------- Final Document ----------
        doc = {
            # Keep both keys for compatibility
            "farmer_id": farmer_id,
            "farmerId": farmer_id,

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

            "crop_detail": crop_details,

            "notes": notes,
        }

        col.insert_one(doc)

        return {"ok": True, "request_id": doc["request_id"]}

    # -----------------------------
    # FIND STORAGE REQUEST
    # -----------------------------
    @staticmethod
    def _find_storage_request_for_farmer(
        farmer_id: str,
        request_id: str
    ) -> Optional[Dict[str, Any]]:

        col = get_col("farmer_request")
        if col is None:
            return None

        base = {
            "requestKind": "storage",
            "$or": [
                {"farmerId": farmer_id},
                {"farmer_id": farmer_id},
            ]
        }

        # 1) by Mongo _id
        if ObjectId.is_valid(request_id):
            doc = col.find_one({**base, "_id": ObjectId(request_id)})
            if doc:
                return doc

        # 2) by request_id string (your generated id)
        return (
            col.find_one({**base, "request_id": request_id})
            or col.find_one({**base, "requestId": request_id})
        )

    # -----------------------------
    # FIND WAREHOUSE USER
    # -----------------------------
    @staticmethod
    def _find_warehouse_user(warehouse_id: str) -> Optional[Dict[str, Any]]:
        users = get_col("users")
        if users is None:
            return None

        u = users.find_one({"userId": warehouse_id})
        if not u:
            u = users.find_one({"warehouseId": warehouse_id})
        return u

    # -----------------------------
    # INVENTORY NORMALIZATION
    # -----------------------------
    @staticmethod
    def _flatten_inventory_docs(inv_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for d in inv_docs:
            if isinstance(d.get("crops"), list):
                out.extend(d["crops"])
            else:
                out.append(d)
        return out

    @staticmethod
    def _get_inventory_for_warehouse(
        warehouse_id: str,
        farmer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        inv_col = get_col("warehouse_inventory")
        if inv_col is None:
            return []

        q = {"warehouseId": warehouse_id}

        # support both farmerId and farmer_id in inventory too
        if farmer_id:
            q = {
                "warehouseId": warehouse_id,
                "$or": [
                    {"farmerId": farmer_id},
                    {"farmer_id": farmer_id},
                ]
            }

        inv_docs = list(inv_col.find(q).sort([("storedOn", -1), ("created_at", -1)]))
        return FarmerStorageService._flatten_inventory_docs(inv_docs)

    @staticmethod
    def _normalize_inventory_crop(c: Dict[str, Any]) -> Dict[str, Any]:
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

    # -----------------------------
    # WAREHOUSE INFO PAGE DATA
    # -----------------------------
    @staticmethod
    def get_warehouse_info_page_data(
        farmer_id: str,
        warehouse_id: str
    ) -> Dict[str, Any]:

        if not warehouse_id:
            return {"ok": False, "error": "warehouse_id is required."}

        u = FarmerStorageService._find_warehouse_user(warehouse_id)
        if not u:
            return {"ok": False, "error": "Warehouse not found in users collection (or Mongo disabled)."}

        ss0 = {}
        if isinstance(u.get("storage_services"), list) and u["storage_services"]:
            ss0 = u["storage_services"][0] or {}

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
