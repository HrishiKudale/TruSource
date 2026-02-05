# backend/services/farmer/crop_service.py

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List
import json

from backend.mongo import mongo
from backend.blockchain import (
    get_crop_history,
    get_user_crops,
    register_crop_onchain,
)
from backend.models.farmer.crop_models import CropRegistrationModel, CropInfoModel
from backend.mongo_safe import get_db
from backend.mongo_safe import get_col

class CropService:
    # ------------------------------------------------------------
    # MY CROPS – DASHBOARD AGGREGATES
    # ------------------------------------------------------------
    @staticmethod
    def get_my_crops(farmer_id: str) -> Dict[str, Any]:
        crops: List[Dict[str, Any]] = []
        total_area = 0
        total_harvest_qtl = 0
        total_sold_qtl = 0

        try:
            crop_ids = get_user_crops(farmer_id) or []
        except Exception as e:
            print(f"[CropService.get_my_crops] Error get_user_crops: {e}")
            crop_ids = []

        # ✅ IMPORTANT: remove duplicate crop IDs
        seen = set()
        unique_crop_ids = []
        for cid in crop_ids:
            cid = str(cid or "").strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            unique_crop_ids.append(cid)

        for cid in unique_crop_ids:
            try:
                history = get_crop_history(cid) or []
            except Exception as e:
                print(f"[CropService.get_my_crops] Error get_crop_history({cid}): {e}")
                continue

            planted = None
            harvested = None
            sold_qty = 0

            for ev in history:
                status = ev[0]

                if status == "Planted":
                    planted = {
                        "id": cid,
                        "name": ev[14],
                        "crop_type": ev[16],
                        "crop_name": ev[17],
                        "date_planted": ev[6],
                        "farming_type": ev[4] if len(ev) > 5 else "",
                        "seed_type": ev[5] if len(ev) > 6 else "",
                        "area_size": int(ev[13] or 0),
                    }

                elif status == "Harvested":
                    harvested = {
                        "harvest_date": ev[5],
                        "harvest_qty": int(ev[12] or 0),
                        "packaging_type": ev[10],
                    }

                elif status in ("Sold", "Retail", "Retailer"):
                    sold_qty += int(ev[18] or 0)

            # ✅ add exactly ONE row per crop id
            if planted:
                crops.append(
                    {
                        "id": planted["id"],
                        "name": planted["name"],
                        "crop_type": planted["crop_type"],
                        "crop_name": planted["crop_name"],
                        "date_planted": planted["date_planted"],
                        "farming_type": planted["farming_type"],
                        "seed_type": planted["seed_type"],
                        "harvest_date": harvested["harvest_date"] if harvested else "",
                        "total_quantity": harvested["harvest_qty"] if harvested else 0,
                        "status": "Harvested" if harvested else "Planted",
                    }
                )

                # ✅ totals should be counted ONCE per crop (not inside history loop)
                total_area += int(planted.get("area_size") or 0)
                if harvested:
                    total_harvest_qtl += int(harvested.get("harvest_qty") or 0)
                total_sold_qtl += int(sold_qty or 0)

        return {
            "crops": crops,
            "total_crops": len(crops),
            "total_area_acres": total_area,
            "total_harvest_qtl": total_harvest_qtl,
            "total_sold_qtl": total_sold_qtl,
        }


    # ------------------------------------------------------------
    # SINGLE CROP DETAIL (for CropInfo.html or JSON)
    # ------------------------------------------------------------
    @staticmethod
    def get_crop_detail(farmer_id: str, crop_id: str) -> Dict[str, Any]:

        try:
            history = get_crop_history(crop_id) or []
        except Exception as e:
            print(f"[CropService.get_crop_detail] Error get_crop_history({crop_id}): {e}")
            history = []

        planted = None
        harvested = None
        sold_qty = 0

        for ev in history:
            status = ev[0]

            if status == "Planted":
                planted = {
                    "id": crop_id,
                    "name": ev[14],
                    "crop_type": ev[16],
                    "crop_name":ev[17],
                    "date_planted": ev[6],
                    "farming_type": ev[4] if len(ev) > 5 else "",
                    "seed_type": ev[5] if len(ev) > 6 else "",
                    "area_size": int(ev[13]),
                    "timestamp": int(ev[3]),
                    "location": ev[1],
                    "farmer_name":ev[2]
                }

            if status == "Harvested":
                harvested = {
                    "harvest_date": ev[5],
                    "harvest_qty": int(ev[12]),
                    "packaging_type": ev[10]
                }

            if status in ("Sold", "Retail", "Retailer"):
                qty = int(ev[18] or 0)
                sold_qty += qty

        crop = {
            "id": planted["id"] if planted else crop_id,
            "name": planted["name"] if planted else "",
            "crop_type": planted["crop_type"] if planted else "",
            "crop_name": planted["crop_name"] if planted else "",
            "date_planted": planted["date_planted"] if planted else "",
            "farming_type": planted["farming_type"] if planted else "",
            "seed_type": planted["seed_type"] if planted else "",
            "harvest_date": harvested["harvest_date"] if harvested else "",
            "packaging_type": harvested["packaging_type"] if harvested else "",
            "total_quantity": harvested["harvest_qty"] if harvested else 0,
            "status": "Harvested" if harvested else "Planted",
            "sold_quantity": sold_qty,
            "area_size": planted["area_size"] if planted else 0,
            "timestamp": planted["timestamp"] if planted else None,
            "location": planted["location"]

        }


        return crop

    # ------------------------------------------------------------
    # BASIC HELPERS (legacy-compatible)
    # ------------------------------------------------------------
    @staticmethod
    def get_crop_ids(farmer_id: str):
        try:
            crop_ids = get_user_crops(farmer_id)
            return crop_ids
        except Exception:
            return []

    @staticmethod
    def get_crop_info(crop_id: str) -> CropInfoModel:
        history = get_crop_history(crop_id)
        planted = None
        harvested = None
        sold_qty = 0

        for ev in history:
            status = ev[0]

            if status == "Planted":
                planted = {
                    "cropId": crop_id,
                    "cropType": ev[16],
                    "cropName": ev[17],
                    "farmingType": ev[5],
                    "seedType": ev[6],
                    "datePlanted": ev[4],
                    "areaSize": ev[13],
                    "timestamp": ev[3],
                }

            if status == "Harvested":
                harvested = {
                    "harvestDate": ev[5],
                    "harvestedQty": ev[12],
                }

            if status in ("Sold", "Retail", "Retailer"):
                sold_qty += int(ev[18] or 0)

        if planted:
            planted["harvestDate"] = harvested["harvestDate"] if harvested else None
            planted["harvestedQty"] = harvested["harvestedQty"] if harvested else 0
            planted["soldQty"] = sold_qty

            # convert timestamp
            try:
                planted["timestamp"] = datetime.utcfromtimestamp(
                    int(planted["timestamp"])
                ).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            return CropInfoModel(**planted)

        return CropInfoModel(
            cropId=crop_id,
            cropType="Unknown",
            farmingType=None,
            seedType=None,
            datePlanted=None,
            harvestDate=None,
            harvestedQty=0,
            soldQty=0,
            areaSize=0,
            timestamp=None,
        )

    # ============================================================
    # SAVE COORDINATES + REGISTER CROP (ONE FLOW)
    # ============================================================

    @staticmethod
    def register_crop_with_blockchain(
        farmer_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:

        # --- 1) Normalize keys ---
        crop_id = payload.get("cropId") or payload.get("crop_id")
        crop_type = payload.get("cropType") or payload.get("crop_type")
        crop_name = payload.get("cropName") or payload.get("crop_name")
        date_planted = payload.get("datePlanted") or payload.get("date_planted")
        farming_type = payload.get("farmingType") or payload.get("farming_type")
        seed_type = payload.get("seedType") or payload.get("seed_type")
        location = payload.get("location") or ""
        farmer_name = payload.get("farmerName") or payload.get("farmer_name") or ""
        area_size = payload.get("areaSize") or payload.get("area_size") or 0

        coords = payload.get("coordinates")
        if isinstance(coords, str):
            try:
                coords = json.loads(coords)
            except Exception:
                coords = None

        # --- 2) Validate with Pydantic ---
        model = CropRegistrationModel(
            farmerId=farmer_id,
            cropId=crop_id,
            cropType=crop_type,
            cropName=crop_name,
            farmingType=farming_type,
            seedType=seed_type,
            areaSize=float(area_size or 0) if area_size not in ("", None) else None,
            datePlanted=date_planted,
            coordinates=coords,
        )

        # --- 3) Save farm coordinates to Mongo (SAFE) ---
        inserted_id = None
        farm_col = get_col("farm_coordinates")

        farm_doc = {
            "user_id": farmer_id,
            "crop_id": model.cropId,
            "cropType": model.cropType,
            "cropName": crop_name,
            "area_size": str(model.areaSize) if model.areaSize is not None else None,
            "date_planted": model.datePlanted,
            "coordinates": model.coordinates or [],
            "created_at": datetime.utcnow(),
        }

        if farm_col is not None:
            try:
                res = farm_col.insert_one(farm_doc)
                inserted_id = res.inserted_id
            except Exception as e:
                print(f"⚠️ Mongo insert farm_coordinates failed: {e}")
        else:
            print("⚠️ Mongo disabled/unavailable: skipping farm_coordinates insert")


        # --- 4) Register crop ON-CHAIN ---
        tx_hash = register_crop_onchain(
            user_id=model.farmerId,
            crop_id=model.cropId,
            crop_type=model.cropType,
            crop_name=crop_name or "",
            farmer_name=farmer_name or "",
            date_planted=model.datePlanted or "",
            farming_type=model.farmingType or "",
            seed_type=model.seedType or "",
            location=location or "",
            area_size=model.areaSize or 0,
        )

        # --- 5) Back-link tx hash in Mongo (SAFE) ---
        if farm_col is not None and inserted_id is not None:
            try:
                farm_col.update_one(
                    {"_id": inserted_id},
                    {"$set": {"txHash": tx_hash, "updated_at": datetime.utcnow()}},
                )
            except Exception as e:
                print(f"⚠️ Mongo update txHash failed: {e}")
        else:
            print("⚠️ Skipping txHash update (Mongo off or insert missing)")


        return {
            "ok": True,
            "cropId": model.cropId,
            "txHash": tx_hash,
            "mongo_saved": bool(inserted_id),
        }


    # ------------------------------------------------------------
    # JUST save coordinates (no blockchain) – optional helper
    # ------------------------------------------------------------

    @staticmethod
    def save_coordinates_only(
        farmer_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:

        normalized = {
            "farmerId": farmer_id,
            "cropId": payload.get("cropId"),
            "cropType": payload.get("cropType"),
            "farmerName": payload.get("farmerName")
            or payload.get("farmer_name")
            or "",
            "datePlanted": payload.get("date_planted") or payload.get("datePlanted"),
            "farmingType": payload.get("farmingType"),
            "seedType": payload.get("seedType"),
            "location": payload.get("location") or "",
            "areaSize": float(payload.get("area_size") or 0),
            "coordinates": payload.get("coordinates") or [],
        }

        try:
            reg = CropRegistrationModel(**normalized)
        except Exception as e:
            return {"ok": False, "err": f"invalid payload: {e}"}

        if not reg.coordinates or len(reg.coordinates) < 3:
            return {"ok": False, "err": "invalid polygon: at least 3 points required"}

        doc = {
            "user_id": reg.farmerId,
            "crop_id": reg.cropId,
            "cropType": reg.cropType,
            "area_size": str(reg.areaSize or ""),
            "date_planted": reg.datePlanted,
            "coordinates": reg.coordinates,
            "created_at": datetime.utcnow(),
        }

        col = get_col("farm_coordinates")
        if col is None:
            return {"ok": False, "err": "MongoDB is disabled or unavailable"}


        col.insert_one(doc)
        return {"ok": True, "cropId": reg.cropId}



    @staticmethod
    def get_crop_activity_timeline(farmer_id: str, crop_id: str):
        """
        Returns ordered list of timeline steps.
        Safe when Mongo is disabled/unavailable.
        """

        # ====== Base step: Crop Registered (onchain / crop doc) ======
        crop = CropService.get_crop_detail(farmer_id, crop_id)  # dict

        timeline = []

        def _dt(x):
            if not x:
                return ""
            return str(x)

        # 1) Crop Registered
        timeline.append({
            "key": "crop_registered",
            "title": "Crop Registered",
            "desc": "You registered this crop successfully.",
            "at": _dt(crop.get("date_planted", "")),
            "link": None,
            "is_done": True
        })

        # 2) Harvesting
        harvest_date = crop.get("harvest_date", "") or ""
        status = crop.get("status", "") or ""
        harvested_done = status in (
            "Harvested", "Stored", "Listed", "OrderRequested", "OrderCreated",
            "Dispatched", "Sold", "PaymentReceived", "Paid"
        )
        timeline.append({
            "key": "harvesting",
            "title": "Harvesting",
            "desc": "Crop harvested and ready for storage or sale.",
            "at": _dt(harvest_date),
            "link": None,
            "is_done": bool(harvest_date) or harvested_done
        })

        # -------------------------
        # Mongo-dependent steps
        # -------------------------
        db = get_db()
        if db is None:
            # Mongo off -> return placeholders for all mongo-based steps
            timeline.extend([
                {
                    "key": "stored_warehouse",
                    "title": "Stored in Warehouse",
                    "desc": "Mongo is disabled, storage status not available.",
                    "at": "",
                    "link": None,
                    "is_done": False
                },
                {
                    "key": "listed_sale",
                    "title": "Listed for Sale",
                    "desc": "Mongo is disabled, marketplace status not available.",
                    "at": "",
                    "link": None,
                    "is_done": False
                },
                {
                    "key": "order_requested",
                    "title": "Order Requested",
                    "desc": "Mongo is disabled, order status not available.",
                    "at": "",
                    "link": None,
                    "is_done": False
                },
                {
                    "key": "order_created",
                    "title": "Order Created",
                    "desc": "Mongo is disabled, order status not available.",
                    "at": "",
                    "link": None,
                    "is_done": False
                },
                {
                    "key": "dispatched_sold",
                    "title": "Dispatched & Sold",
                    "desc": "Mongo is disabled, shipment status not available.",
                    "at": "",
                    "link": None,
                    "is_done": False
                },
                {
                    "key": "payment_received",
                    "title": "Payment Received",
                    "desc": "Mongo is disabled, payment status not available.",
                    "at": "",
                    "link": None,
                    "is_done": False
                },
            ])
            return timeline

        # 3) Stored in Warehouse (farmer_request requestKind=storage)
        storage_req = db.farmer_request.find_one(
            {
                "$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}],
                "$or": [{"crop_id": crop_id}, {"cropId": crop_id}],
                "$or": [{"requestKind": "storage"}, {"request_kind": "storage"}],
            },
            sort=[("created_at", -1)]
        )

        if storage_req:
            timeline.append({
                "key": "stored_warehouse",
                "title": "Stored in Warehouse",
                "desc": "Crop stored successfully.",
                "at": _dt(storage_req.get("created_at")),
                "link": "/farmer/storage/warehouse/",
                "is_done": True
            })
        else:
            timeline.append({
                "key": "stored_warehouse",
                "title": "Stored in Warehouse",
                "desc": "No warehouse storage request created yet.",
                "at": "",
                "link": None,
                "is_done": False
            })

        # 4) Listed for Sale (marketplace / market_place / marketplace_requests)
        market_req = None
        for col_name in ("marketplace", "market_place", "marketplace_requests"):
            try:
                market_req = db[col_name].find_one(
                    {
                        "$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}],
                        "$or": [{"crop_id": crop_id}, {"cropId": crop_id}],
                    },
                    sort=[("created_at", -1)]
                )
                if market_req:
                    break
            except Exception:
                continue

        if market_req:
            timeline.append({
                "key": "listed_sale",
                "title": "Listed for Sale",
                "desc": "Crop listed successfully in marketplace.",
                "at": _dt(market_req.get("created_at")),
                "link": "/farmer/marketplace",
                "is_done": True
            })
        else:
            timeline.append({
                "key": "listed_sale",
                "title": "Listed for Sale",
                "desc": "Not listed in marketplace yet.",
                "at": "",
                "link": None,
                "is_done": False
            })

        # 5/6/7/8 order flow (farmer_orders)
        order = db.farmer_orders.find_one(
            {
                "$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}],
                "$or": [{"crop_id": crop_id}, {"cropId": crop_id}],
            },
            sort=[("created_at", -1)]
        )

        if order:
            order_id = order.get("orderId") or order.get("order_id") or order.get("orderCode") or ""
            order_status = (order.get("status") or "").lower()

            timeline.append({
                "key": "order_requested",
                "title": "Order Requested",
                "desc": f"Request sent to buyer {order_id}".strip(),
                "at": _dt(order.get("created_at")),
                "link": f"/farmer/orders/{order_id}" if order_id else None,
                "is_done": True
            })

            timeline.append({
                "key": "order_created",
                "title": "Order Created",
                "desc": "Buyer order received.",
                "at": _dt(order.get("created_at")),
                "link": f"/farmer/orders/{order_id}" if order_id else None,
                "is_done": True
            })

            # Shipment from transporter_request (or transport_request)
            ship = None
            for col_name in ("transporter_request", "transport_request"):
                try:
                    ship = db[col_name].find_one(
                        {
                            "$or": [{"farmer_id": farmer_id}, {"farmerId": farmer_id}],
                            "$or": [{"crop_id": crop_id}, {"cropId": crop_id}],
                        },
                        sort=[("created_at", -1)]
                    )
                    if ship:
                        break
                except Exception:
                    continue

            if ship:
                timeline.append({
                    "key": "dispatched_sold",
                    "title": "Dispatched & Sold",
                    "desc": "Order confirmed and dispatched.",
                    "at": _dt(ship.get("created_at")),
                    "link": "/farmer/shipments",
                    "is_done": True
                })
            else:
                timeline.append({
                    "key": "dispatched_sold",
                    "title": "Dispatched & Sold",
                    "desc": "Shipment not created yet.",
                    "at": "",
                    "link": None,
                    "is_done": False
                })

            paid = order_status in ("paid", "payment_received", "completed", "success")
            timeline.append({
                "key": "payment_received",
                "title": "Payment Received",
                "desc": "Payment received successfully & verified." if paid else "Payment pending.",
                "at": _dt(order.get("payment_date") or order.get("updated_at") or ""),
                "link": f"/farmer/orders/{order_id}" if order_id else None,
                "is_done": paid
            })

        else:
            for key, title, desc in [
                ("order_requested", "Order Requested", "No buyer request yet."),
                ("order_created", "Order Created", "No buyer order yet."),
                ("dispatched_sold", "Dispatched & Sold", "Not dispatched yet."),
                ("payment_received", "Payment Received", "Payment not received yet.")
            ]:
                timeline.append({
                    "key": key, "title": title, "desc": desc,
                    "at": "", "link": None, "is_done": False
                })

        return timeline

