# backend/services/farmer/lot_service.py
from datetime import datetime
from backend.mongo import mongo
from backend.models.farmer.lot_models import CompositeLotCreateModel


class LotService:

    @staticmethod
    def create_composite_lot(payload: CompositeLotCreateModel, farmer_id: str):
        now = datetime.utcnow()
        lot_id = f"LOT-{now.strftime('%Y%m%d')}-{str(now.timestamp()).replace('.', '')[-5:]}"

        data = payload.dict()
        doc = {
            "compositeLotId": lot_id,
            "farmerId": farmer_id,
            "created_at": now,
            "updated_at": now,
            **data
        }

        mongo.db.composite_lots.insert_one(doc)
        return {"ok": True, "compositeLotId": lot_id}

    @staticmethod
    def list_composite_lots(farmer_id: str, limit: int = 50):
        cur = (
            mongo.db.composite_lots
            .find({"farmerId": farmer_id})
            .sort([("created_at", -1)])
            .limit(limit)
        )

        items = []
        for d in cur:
            d["_id"] = str(d["_id"])
            items.append(d)

        return {"ok": True, "items": items}
