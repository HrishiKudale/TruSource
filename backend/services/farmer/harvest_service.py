# backend/services/farmer/harvest_service.py

from datetime import datetime, timezone
import json
from typing import Any, Dict
from backend.blockchain import register_crop_onchain, register_harvest_onchain
from backend.models.farmer.harvest_record import HarvestRecordModel
from backend.mongo import mongo
import qrcode
import os


class HarvestService:

    @staticmethod
    def record_harvest(farmer_id: str, payload: dict):
        now = datetime.utcnow()
        batch_id = f"BATCH-{int(now.timestamp())}"

        doc = {
            "batchId": batch_id,
            "farmerId": farmer_id,
            "created_at": now,
            **payload
        }

        mongo.db.harvest_batches.insert_one(doc)

        # generate QR
        qr_url = f"/farmer/harvest/qr/download/{batch_id}"
        os.makedirs("static/qrcodes", exist_ok=True)
        file_path = f"static/qrcodes/{batch_id}.png"
        qrcode.make(qr_url).save(file_path)

        mongo.db.qr_codes.insert_one({
            "batchId": batch_id,
            "farmerId": farmer_id,
            "path": file_path
        })

        return {"ok": True, "batchId": batch_id}

    @staticmethod
    def get_qr_labels(farmer_id: str):
        cur = mongo.db.qr_codes.find({"farmerId": farmer_id})
        items = []
        for x in cur:
            x["_id"] = str(x["_id"])
            items.append(x)
        return {"ok": True, "items": items}

    @staticmethod
    def download_qr(batch_id: str):
        path = f"static/qrcodes/{batch_id}.png"
        if not os.path.exists(path):
            return {"ok": False, "err": "QR not found"}
        return {"ok": True, "file": path}

    @staticmethod
    def list_bags(farmer_id: str):
        cur = mongo.db.harvest_bags.find({"farmerId": farmer_id})
        bags = []
        for b in cur:
            b["_id"] = str(b["_id"])
            bags.append(b)
        return {"ok": True, "bags": bags}

    @staticmethod
    def add_bag(farmer_id: str, payload: dict):
        doc = {
            "farmerId": farmer_id,
            **payload
        }
        mongo.db.harvest_bags.insert_one(doc)
        return {"ok": True}

    @staticmethod
    def delete_bag(farmer_id: str, bag_id: str):
        mongo.db.harvest_bags.delete_one({"farmerId": farmer_id, "_id": bag_id})
        return {"ok": True}



    @staticmethod
    def register_harvest_with_blockchain(farmer_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = payload or {}
        payload["farmerId"] = farmer_id

        # ✅ Normalize payload keys
        payload["cropId"] = payload.get("cropId") or payload.get("crop_id")


        payload["harvesterName"] = payload.get("harvesterName") or payload.get("farmerName") or ""

        # harvestQuantity can come as harvestQuantity or quantityValue
        if payload.get("harvestQuantity") is None and payload.get("quantityValue") is not None:
            payload["harvestQuantity"] = payload.get("quantityValue")


        # ✅ Validate
        model = HarvestRecordModel(**payload)

        now = datetime.now(timezone.utc)

        # ✅ Save to Mongo: harvest_batches
        harvest_doc = {
            "farmerId": model.farmerId,
            "cropId": model.cropId,
            "harvestDate": model.harvestDate,
            "harvesterName": model.harvesterName or "",
            "harvestQuantity": float(model.harvestQuantity or 0),
            "packagingType": model.packagingType or "",
            "status": "harvest_registered",
            "created_at": now,
            "updated_at": now,
        }

        insert_res = mongo.db.harvest_batches.insert_one(harvest_doc)


        # ✅ Register on-chain (match your blockchain function signature)
        tx_hash = register_harvest_onchain(
            user_id=model.farmerId,
            crop_id=model.cropId,
            harvester_name=model.harvesterName or "",
            harvest_date=model.harvestDate,
            harvest_quantity=model.harvestQuantity or 0,
            packaging_type=model.packagingType or "",
        )

        mongo.db.harvest_batches.update_one(
            {"_id": insert_res.inserted_id},
            {"$set": {"txHash": tx_hash, "updated_at": datetime.now(timezone.utc)}},
        )

        return {
            "ok": True,
            "harvestId": str(insert_res.inserted_id),
            "cropId": model.cropId,
            "txHash": tx_hash,
        }
