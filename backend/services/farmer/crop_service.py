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

        for cid in crop_ids:
            try:
                history = get_crop_history(cid) or []
            except Exception as e:
                print(f"[CropService.get_my_crops] Error get_crop_history({cid}): {e}")
                continue

            planted = None
            harvested = None
            sold_qty = 0

            for ev in history:
                # Assumes the same event layout as your original on-chain struct
                status = ev[0]

                if status == "Planted":
                    planted = {
                        "id": cid,
                        "name": ev[14],          # cropType display name
                        "crop_type": ev[16],
                        "crop_name":ev[17],     # variety / type
                        "date_planted": ev[6],
                        "farming_type": ev[4] if len(ev) > 5 else "",
                        "seed_type": ev[5] if len(ev) > 6 else "",
                        "area_size": int(ev[13]),
                    }
                    total_area += int(ev[13])

                if status == "Harvested":
                    harvested = {
                        "harvest_date": ev[5],
                        "harvest_qty": int(ev[12]),
                        "packaging_type": ev[10]
                    }
                    total_harvest_qtl += int(ev[12])

                if status in ("Sold", "Retail", "Retailer"):
                    qty = int(ev[18] or 0)
                    sold_qty += qty
                    total_sold_qtl += qty

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
        # --- 1. Normalize keys from your payload ---
        crop_id = payload.get("cropId") or payload.get("crop_id")
        crop_type = (
            payload.get("cropType")
            or payload.get("crop_type")
        )
        crop_name= payload.get("cropName")
        date_planted = payload.get("datePlanted") or payload.get("date_planted")
        farming_type = payload.get("farmingType") or payload.get("farming_type")
        seed_type = payload.get("seedType") or payload.get("seed_type")
        location = payload.get("location") or ""
        farmer_name = (
            payload.get("farmerName")
            or payload.get("farmer_name")
            or ""
        )
        area_size = (
            payload.get("areaSize")
            or payload.get("area_size")
            or 0
        )

        coords = payload.get("coordinates")
        # coordinates may arrive as JSON string
        if isinstance(coords, str):
            try:
                coords = json.loads(coords)
            except Exception:
                coords = None

        # --- 2. Validate via Pydantic model ---
        model = CropRegistrationModel(
            farmerId=farmer_id,
            cropId=crop_id,
            cropType=crop_type,
            cropName=crop_name,
            farmingType=farming_type,
            seedType=seed_type,
            areaSize=float(area_size or 0)
            if area_size not in ("", None)
            else None,
            datePlanted=date_planted,
            coordinates=coords,
        )

        # --- 3. Save farm coordinates to Mongo (farm_coordinates collection) ---
        farm_doc = {
            "user_id": farmer_id,
            "crop_id": model.cropId,
            "cropType": model.cropType,
            "area_size": str(model.areaSize) if model.areaSize is not None else None,
            "date_planted": model.datePlanted,
            "coordinates": model.coordinates or [],
            "created_at": datetime.utcnow(),
        }
        insert_res = mongo.db.farm_coordinates.insert_one(farm_doc)

        # --- 4. Register crop ON-CHAIN ---
        tx_hash = register_crop_onchain(
            user_id=model.farmerId,
            crop_id=model.cropId,
            crop_type=model.cropType,
            crop_name=crop_name,
            farmer_name=farmer_name,
            date_planted=model.datePlanted or "",
            farming_type=model.farmingType,
            seed_type=model.seedType,
            location=location,
            area_size=model.areaSize or 0,
        )

        # Optionally, back-link tx hash
        mongo.db.farm_coordinates.update_one(
            {"_id": insert_res.inserted_id},
            {"$set": {"txHash": tx_hash}},
        )

        return {
            "ok": True,
            "cropId": model.cropId,
            "txHash": tx_hash,
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

        mongo.db.farm_coordinates.insert_one(doc)
        return {"ok": True, "cropId": reg.cropId}


    @staticmethod
    def get_crop_activity_timeline(farmer_id: str, crop_id: str):
        """
        Returns ordered list of timeline steps.
        Each item:
          key, title, desc, at (datetime string), link(optional), is_done(bool)
        """

        # ====== Base step: Crop Registered (onchain / crop doc) ======
        crop = CropService.get_crop_detail(farmer_id, crop_id)  # your existing function

        timeline = []

        # helpers
        def _dt(x):
            if not x:
                return ""
            return str(x)

        # 1) Crop Registered
        timeline.append({
            "key": "crop_registered",
            "title": "Crop Registered",
            "desc": "You registered this crop successfully.",
            "at": _dt(getattr(crop, "date_planted", None) or crop.get("date_planted") if isinstance(crop, dict) else ""),
            "link": None,
            "is_done": True
        })

        # 2) Harvesting (only if harvested)
        harvest_date = (crop.get("harvest_date") if isinstance(crop, dict) else getattr(crop, "harvest_date", "")) or ""
        total_qty = (crop.get("total_quantity") if isinstance(crop, dict) else getattr(crop, "total_quantity", 0)) or 0
        status = (crop.get("status") if isinstance(crop, dict) else getattr(crop, "status", "")) or ""

        harvested_done = status in ("Harvested", "Stored", "Listed", "OrderRequested", "OrderCreated", "Dispatched", "Sold", "PaymentReceived", "Paid")
        timeline.append({
            "key": "harvesting",
            "title": "Harvesting",
            "desc": f"Crop harvested and ready for storage or sale.",
            "at": _dt(harvest_date),
            "link": None,
            "is_done": bool(harvest_date) or harvested_done
        })

        # ====== Mongo lookups (adjust fields if your schema differs) ======

        # 3) Stored in Warehouse (farmer_request requestKind=storage)
        storage_req = mongo.db.farmer_request.find_one(
            {"farmer_id": farmer_id, "crop_id": crop_id, "requestKind": "storage"},
            sort=[("created_at", -1)]
        )
        if storage_req:
            st = storage_req.get("status", "")
            timeline.append({
                "key": "stored_warehouse",
                "title": "Stored in Warehouse",
                "desc": "Crop stored successfully.",
                "at": _dt(storage_req.get("created_at")),
                "link": "/farmer/storage/warehouse/" if st else None,
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

        # 4) Listed for Sale (marketplace_requests)
        market_req = mongo.db.marketplace.find_one(
            {"farmerId": farmer_id, "cropId": crop_id},
            sort=[("created_at", -1)]
        )
        if market_req:
            timeline.append({
                "key": "listed_sale",
                "title": "Listed for Sale",
                "desc": "Crop listed successfully in marketplace.",
                "at": _dt(market_req.get("created_at")),
                "link": "/farmer/marketplace" ,
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
        order = mongo.db.farmer_orders.find_one(
            {"farmerId": farmer_id, "cropId": crop_id},
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

            # Shipment from transporter_request
            ship = mongo.db.transporter_request.find_one(
                {"cropId": crop_id, "farmerId": farmer_id},
                sort=[("created_at", -1)]
            )
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

            paid = order_status in ("paid", "payment_received", "completed")
            timeline.append({
                "key": "payment_received",
                "title": "Payment Received",
                "desc": "Payment received successfully & verified." if paid else "Payment pending.",
                "at": _dt(order.get("payment_date") or order.get("updated_at") or ""),
                "link": f"/farmer/orders/{order_id}" if order_id else None,
                "is_done": paid
            })

        else:
            # placeholders if no order
            for key, title, desc in [
                ("order_requested","Order Requested","No buyer request yet."),
                ("order_created","Order Created","No buyer order yet."),
                ("dispatched_sold","Dispatched & Sold","Not dispatched yet."),
                ("payment_received","Payment Received","Payment not received yet.")
            ]:
                timeline.append({"key": key, "title": title, "desc": desc, "at": "", "link": None, "is_done": False})

        return timeline
