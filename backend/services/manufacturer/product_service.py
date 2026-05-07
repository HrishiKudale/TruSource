
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

class ProductService:
    #
    # MY OPERATIONS
    #
    @staticmethod
    def get_my_operations(manufacturer_id: str) -> Dict[str,Any]:
        products: List[Dict[str, Any]] = []
        total_products = 0
        requested_products = 0
        active_operations = 0
        processed_operations = 0

        try:
            crop_ids = get_user_crops(manufacturer_id) or []
        except Exception as e:
            print(f"[ProductService.get_my_operations] Error get_user_crops:{e}")
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