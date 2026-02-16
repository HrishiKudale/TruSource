# backend/services/traceability/traceability_services.py
from typing import Any, Dict, List, Optional

from backend.blockchain import contract  # your existing wiring
from backend.models.traceability.traceability_models import (
    TraceabilityViewModel,
    OriginHarvestBlock,
    StorageBlock,
    ProcessingBlock,
    ShipmentBlock,
    ShipmentItem,
    SaleBlock,
)
from backend.mongo import mongo
# You likely already have mongo in app context
# We'll import lazily inside functions to avoid circular imports


class TraceabilityService:
    """
    Compose traceability timeline data:
      - On-chain: crop + history (Planted/Harvested/Processed/Distributed/Sold)
      - Mongo: storage + shipments (warehouse/transporter not on chain)
    """

    # -------------------------
    # Public API
    # -------------------------
    @staticmethod
    def build_traceability(crop_id: str, user_id: Optional[str] = None) -> TraceabilityViewModel:
        vm = TraceabilityViewModel(cropId=crop_id)

        crop = TraceabilityService._get_crop_onchain(crop_id)
        hist = TraceabilityService._get_history_onchain(crop_id)

        # 1) Origin + Harvest (mostly crop fields + harvest event)
        vm.originHarvest = TraceabilityService._compose_origin_harvest(crop, hist)

        # 2) Processing (manufacturer event)
        proc = TraceabilityService._compose_processing(hist)
        if proc:
            vm.processing = proc

        # 3) Sale (retailer event)
        sale = TraceabilityService._compose_sale(hist)
        if sale:
            vm.sale = sale

        # 4) Storage (Mongo)
        storage = TraceabilityService._get_storage_mongo(crop_id, user_id=user_id)
        if storage:
            vm.storage = storage

        # 5) Shipments (Mongo)
        shipments = TraceabilityService._get_shipments_mongo(crop_id, user_id=user_id)
        if shipments and shipments.shipments:
            vm.shipment = shipments

        # Optional debug
        vm.debug = {
            "hasOnchainCrop": bool(crop),
            "onchainHistoryCount": len(hist),
            "hasStorageMongo": bool(storage),
            "shipmentCount": len(shipments.shipments) if shipments else 0,
        }
        return vm

    # -------------------------
    # Blockchain reads
    # -------------------------
    @staticmethod
    def _get_crop_onchain(crop_id: str) -> Dict[str, Any]:
        """
        Your contract getCrop returns tuple.
        Your current trace.sol returns:
          (cropId, cropType, farmerName, farmingType, seedType, location, datePlanted, harvestDate, areaSize)
        If you later add cropName, update mapping here.
        """
        try:
            t = contract.functions.getCrop(crop_id).call()
            # Defensive mapping (by your current contract)
            return {
                "cropId": t[0] if len(t) > 0 else crop_id,
                "cropType": t[1] if len(t) > 1 else "",
                "cropName": t[2] if len(t) > 2 else "",
                "farmerName": t[3] if len(t) > 3 else "",
                "farmingType": t[4] if len(t) > 4 else "",
                "seedType": t[5] if len(t) > 5 else "",
                "location": t[6] if len(t) > 6 else "",
                "datePlanted": t[7] if len(t) > 7 else "",
                "harvestDate": t[8] if len(t) > 8 else "",
                "areaSize": int(t[9]) if len(t) > 9 else 0,
            }
        except Exception as e:
            print("getCrop() failed:", str(e))
            return {}

    @staticmethod
    def _get_history_onchain(crop_id: str) -> List[Dict[str, Any]]:
        """
        getCropHistory returns CropEvent[].
        Your CropEvent struct order currently is large; we parse safely by index.
        We only use key parts:
          status, location, actor, timestamp,
          harvestDate, receivedDate, processedDate,
          packagingType, harvesterName,
          harvestQuantity, processedQuantity, batchCode,
          userId, cropId, cropType
        """
        out: List[Dict[str, Any]] = []
        try:
            arr = contract.functions.getCropHistory(crop_id).call()
        except Exception:
            return out

        for ev in arr or []:
            # ev is tuple; parse defensively
            def g(i, default=""):
                return ev[i] if len(ev) > i and ev[i] is not None else default

            def gi(i, default=0):
                v = ev[i] if len(ev) > i else default
                try:
                    return int(v)
                except Exception:
                    return default

            out.append(
                {
                    "status": str(g(0, "")),
                    "location": str(g(1, "")),
                    "actor": str(g(2, "")),
                    "timestamp": gi(3, 0),

                    "farmingType": str(g(4, "")),
                    "seedType": str(g(5, "")),
                    "datePlanted": str(g(6, "")),

                    "harvestDate": str(g(7, "")),
                    "receivedDate": str(g(8, "")),
                    "processedDate": str(g(9, "")),

                    "packagingType": str(g(10, "")),
                    "harvesterName": str(g(11, "")),
                    "harvestQuantity": gi(12, 0),
                    "areaSize": gi(13, 0),

                    "userId": str(g(14, "")),
                    "cropId": str(g(15, "")),
                    "cropType": str(g(16, "")),

                    "processedQuantity": gi(17, 0),
                    "batchCode": str(g(18, "")),

                    # if you later add cropName into event:
                    "cropName": "",
                }
            )

        return out

    # -------------------------
    # Compose blocks from on-chain
    # -------------------------
    @staticmethod
    def _compose_origin_harvest(crop: Dict[str, Any], hist: List[Dict[str, Any]]) -> OriginHarvestBlock:
        crop_name = crop.get("cropName") or ""
        crop_type = crop.get("cropType") or ""

        planted_on = crop.get("datePlanted") or ""
        harvest_date = crop.get("harvestDate") or ""
        farmer_name = crop.get("farmerName") or ""
        location = crop.get("location") or ""
        farming_type = crop.get("farmingType") or ""

        # If harvest event exists, prefer event harvestDate
        for ev in hist:
            if (ev.get("status") or "").lower() == "harvested":
                if ev.get("harvestDate"):
                    harvest_date = ev["harvestDate"]
                break

        return OriginHarvestBlock(
            location=location,
            cropName=crop_name or crop_type,   # ✅ show Wheat instead of Cash Crops
            cropType=crop_type,
            plantedOn=planted_on,
            harvestDate=harvest_date,
            farmingType=farming_type,
            farmerName=farmer_name,
        )


    @staticmethod
    def _compose_processing(hist: List[Dict[str, Any]]) -> Optional[ProcessingBlock]:
        # Find "Processed"
        proc = None
        for ev in reversed(hist):
            if (ev.get("status") or "").lower() == "processed":
                proc = ev
                break
        if not proc:
            return None

        # Your on-chain event stores processedQuantity in processedQuantity
        input_qty = proc.get("harvestQuantity") or 0
        output_qty = proc.get("processedQuantity") or 0
        date = proc.get("processedDate") or proc.get("receivedDate") or ""

        return ProcessingBlock(
            processorName=proc.get("actor") or "",
            process="Processing",  # if you have exact process name in mongo, override there
            inputQty=f"{input_qty} kg" if input_qty else "",
            outputQty=f"{output_qty} kg" if output_qty else "",
            processingDate=date,
        )

    @staticmethod
    def _compose_sale(hist: List[Dict[str, Any]]) -> Optional[SaleBlock]:
        # Find "Sold"
        sold = None
        for ev in reversed(hist):
            if (ev.get("status") or "").lower() == "sold":
                sold = ev
                break
        if not sold:
            return None

        return SaleBlock(
            buyerName=sold.get("actor") or "",
            city=sold.get("location") or "",
            purchaseDate=sold.get("processedDate") or "",  # you used processedDate slot for soldDate
        )

    # -------------------------
    # Mongo reads (warehouse + shipments)
    # -------------------------
    @staticmethod
    def _get_storage_mongo(crop_id: str, user_id: Optional[str] = None) -> Optional[StorageBlock]:
        """
        Expecting a collection like: warehouse_storage / storage_events etc.
        We'll try multiple names so your existing DB still works.
        Document example (you can match):
          { cropId, userId, warehouseName, city, storedOn, qualityCheck }
        """
         # adjust if your mongo instance lives elsewhere

        queries = {"cropId": crop_id}
        if user_id:
            # optional guard to only show own records
            queries["userId"] = user_id

        for col in ["warehouse_storage", "storage_events", "warehouse_events"]:
            try:
                doc = mongo.db[col].find_one(queries, sort=[("storedOn", -1), ("created_at", -1)])
                if doc:
                    return StorageBlock(
                        warehouseName=str(doc.get("warehouseName") or doc.get("warehouse") or ""),
                        city=str(doc.get("city") or doc.get("location") or ""),
                        storedOn=str(doc.get("storedOn") or doc.get("storedDate") or doc.get("date") or ""),
                        qualityCheck=str(doc.get("qualityCheck") or doc.get("qcStatus") or ""),
                    )
            except Exception:
                continue

        return None

    @staticmethod
    def _get_shipments_mongo(crop_id: str, user_id: Optional[str] = None) -> ShipmentBlock:
        """
        Expect shipments stored in Mongo (since transporter isn't on chain).
        Document example:
          { cropId, userId, transporter, deliveredTo, fromCity, toCity, date }
        """

        q = {"cropId": crop_id}
        if user_id:
            q["userId"] = user_id

        items: List[ShipmentItem] = []
        docs: List[Dict[str, Any]] = []

        for col in ["shipments", "shipment_events", "transporter_shipments", "transport_events"]:
            try:
                cur = list(mongo.db[col].find(q).sort([("date", 1), ("created_at", 1)]))
                if cur:
                    docs = cur
                    break
            except Exception:
                continue

        for idx, d in enumerate(docs, start=1):
            from_city = (d.get("fromCity") or d.get("from") or d.get("origin") or "").strip()
            to_city = (d.get("toCity") or d.get("to") or d.get("destination") or "").strip()
            route = ""
            if from_city and to_city:
                route = f"{from_city} → {to_city}"
            elif d.get("route"):
                route = str(d.get("route"))

            items.append(
                ShipmentItem(
                    title=f"Shipment {idx}",
                    transporter=str(d.get("transporter") or d.get("transporterName") or ""),
                    deliveredTo=str(d.get("deliveredTo") or d.get("delivered_to") or ""),
                    route=route,
                    date=str(d.get("date") or d.get("dispatchDate") or d.get("deliveredDate") or ""),
                )
            )

        return ShipmentBlock(shipments=items)

    @staticmethod
    def get_crops_for_user(user_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all crop IDs for a farmer from blockchain
        """
        out = []

        try:
            crop_ids = contract.functions.getCrop(user_id).call()
        except Exception as e:
            print("getCropsByUser failed:", str(e))
            return out

        for cid in crop_ids:
            crop = TraceabilityService._get_crop_onchain(cid)
            if crop:
                out.append({
                    "cropId": crop.get("cropId"),
                    "cropType": crop.get("cropType"),
                    "date_planted": crop.get("datePlanted"),
                    "location": crop.get("location"),
                })

        return out
