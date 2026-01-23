# backend/services/farmer/processing_service.py

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.mongo import mongo
from backend.blockchain import get_crop_history
from backend.models.farmer.processing_models import (
    ProcessingRequestModel,
    ProcessingOnchainEvent,
)


class FarmerProcessingService:
    """
    Combines Mongo farmer_request docs with on-chain 'Processed' events
    for manufacturer processing views.
    """

    # -------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------
    @staticmethod
    def get_processing_overview(farmer_id: str) -> Dict[str, Any]:
        """
        Overview for Processing UI:
        - KPIs (totals)
        - Table rows per farmer_request
        Data = Mongo (farmer_request) + on-chain Processed events (if any).
        """
        rows: List[Dict[str, Any]] = []

        total_requests = 0
        total_harvest_qty = 0.0
        total_processed_qty = 0.0
        active_processing = 0
        completed_requests = 0

        cursor = (
            mongo.db.farmer_request
            .find({"farmerId": farmer_id})
            .sort([("created_at", -1), ("_id", -1)])
        )

        for raw in cursor:
            try:
                req = ProcessingRequestModel(
                    cropId=raw.get("cropId", ""),
                    farmerId=raw.get("farmerId", farmer_id),
                    cropType=raw.get("cropType"),
                    harvestDate=raw.get("harvestDate"),
                    harvestQuantity=float(raw.get("harvestQuantity") or 0),
                    manufacturerId=raw.get("manufacturerId"),
                    packagingType=raw.get("packagingType"),
                    status=raw.get("status", "pending"),
                    rfidEpcs=raw.get("rfidEpcs"),
                    rfidEpc=raw.get("rfidEpc"),
                    bagQty=raw.get("bagQty", 0),
                    created_at=raw.get("created_at"),
                    updated_at=raw.get("updated_at"),
                )
            except Exception as e:
                print(f"[FarmerProcessingService] invalid farmer_request doc: {e}")
                continue

            total_requests += 1
            total_harvest_qty += req.harvestQuantity or 0.0

            crop_id = req.cropId
            crop_type = req.cropType or ""
            manufacturer_id = req.manufacturerId or ""

            # --- On-chain Processed event (if exists)
            onchain_evt = FarmerProcessingService._latest_processed_event(crop_id)

            if onchain_evt:
                processed_qty = onchain_evt.processedQuantity or 0.0
                manufacturer_name = onchain_evt.manufacturerName or ""
                # Table quantity = processed quantity (already at manufacturer)
                total_qty_for_row = processed_qty

                completed_requests += 1
                total_processed_qty += processed_qty
            else:
                processed_qty = 0.0
                manufacturer_name = ""
                # Not processed yet → show harvested quantity instead of blank
                total_qty_for_row = req.harvestQuantity or 0.0
                active_processing += 1

            location = raw.get("location") or ""  # if you add location in Mongo later
            updated_at = raw.get("updated_at") or raw.get("created_at")

            rows.append({
                "manufacturerId": manufacturer_id,
                "manufacturerName": manufacturer_name or "—",
                "location": location or "—",
                "cropType": crop_type,
                "totalQuantity": total_qty_for_row,
                "updated_at": updated_at,
            })

        return {
            "farmerId": farmer_id,
            "kpis": {
                "total_requests": total_requests,
                "active_processing": active_processing,
                "completed_requests": completed_requests,
                "total_processed_qty": round(total_processed_qty, 2),
                # kept for future use if needed
                "total_harvest_qty": round(total_harvest_qty, 2),
            },
            "items": rows,
        }

    @staticmethod
    def get_processing_detail(farmer_id: str, crop_id: str) -> Dict[str, Any]:
        """
        Detail view for a single cropId:
        - Farmer request (Mongo)
        - All Processed on-chain events
        """
        # Mongo doc (farmer_request)
        req_doc = mongo.db.farmer_request.find_one(
            {"farmerId": farmer_id, "cropId": crop_id}
        )

        req: Optional[ProcessingRequestModel] = None
        if req_doc:
            try:
                req = ProcessingRequestModel(
                    cropId=req_doc.get("cropId", crop_id),
                    farmerId=req_doc.get("farmerId", farmer_id),
                    cropType=req_doc.get("cropType"),
                    harvestDate=req_doc.get("harvestDate"),
                    harvestQuantity=float(req_doc.get("harvestQuantity") or 0),
                    manufacturerId=req_doc.get("manufacturerId"),
                    packagingType=req_doc.get("packagingType"),
                    status=req_doc.get("status", "pending"),
                    rfidEpcs=req_doc.get("rfidEpcs"),
                    rfidEpc=req_doc.get("rfidEpc"),
                    bagQty=req_doc.get("bagQty", 0),
                    created_at=req_doc.get("created_at"),
                    updated_at=req_doc.get("updated_at"),
                )
            except Exception as e:
                print(f"[FarmerProcessingService.get_processing_detail] invalid doc: {e}")

        # On-chain history
        try:
            history = get_crop_history(crop_id) or []
        except Exception as e:
            print(f"[FarmerProcessingService.get_processing_detail] chain error: {e}")
            history = []

        processed_events: List[ProcessingOnchainEvent] = []
        for ev in history:
            if not ev or ev[0] != "Processed":
                continue

            evt = FarmerProcessingService._parse_processed_event(crop_id, ev)
            if evt:
                processed_events.append(evt)

        latest_evt = processed_events[-1] if processed_events else None

        return {
            "farmerId": farmer_id,
            "cropId": crop_id,
            "request": req.model_dump() if req else None,
            "processed_events": [e.model_dump() for e in processed_events],
            "latest": latest_evt.model_dump() if latest_evt else None,
        }

    # -------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------
    @staticmethod
    def _latest_processed_event(crop_id: str) -> Optional[ProcessingOnchainEvent]:
        try:
            history = get_crop_history(crop_id) or []
        except Exception as e:
            print(f"[FarmerProcessingService._latest_processed_event] chain error {crop_id}: {e}")
            return None

        last = None
        for ev in history:
            if not ev or ev[0] != "Processed":
                continue
            parsed = FarmerProcessingService._parse_processed_event(crop_id, ev)
            if parsed:
                last = parsed

        return last

    @staticmethod
    def _parse_processed_event(crop_id: str, ev: List[Any]) -> Optional[ProcessingOnchainEvent]:
        """
        Decode your Solidity CropEvent for 'Processed':
        status          = ev[0] == "Processed"
        manufacturer    = ev[2]
        timestamp       = ev[3]
        receivedDate    = ev[8]
        processedDate   = ev[9]
        packagingType   = ev[10]
        harvestQuantity = ev[12]
        userId          = ev[14]
        cropId          = ev[15]
        cropType        = ev[16]
        processedQty    = ev[17]
        batchCode       = ev[18]
        """
        try:
            status = ev[0]
            if status != "Processed":
                return None

            manufacturerName = ev[2] if len(ev) > 2 else ""
            ts_raw = ev[3] if len(ev) > 3 else 0
            receivedDate = ev[8] if len(ev) > 8 else ""
            processedDate = ev[9] if len(ev) > 9 else ""
            packagingType = ev[10] if len(ev) > 10 else ""
            harvestQuantity = float(ev[12] or 0) if len(ev) > 12 else 0
            chain_cropId = ev[15] if len(ev) > 15 else crop_id
            cropType = ev[16] if len(ev) > 16 else ""
            processedQuantity = float(ev[17] or 0) if len(ev) > 17 else 0
            batchCode = ev[18] if len(ev) > 18 else ""

            ts_int = int(ts_raw or 0)
            ts_human = None
            if ts_int > 0:
                try:
                    ts_human = datetime.utcfromtimestamp(ts_int).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    ts_human = str(ts_raw)

            return ProcessingOnchainEvent(
                cropId=chain_cropId,
                cropType=cropType,
                manufacturerName=manufacturerName,
                receivedDate=receivedDate,
                processedDate=processedDate,
                packagingType=packagingType,
                harvestQuantity=harvestQuantity,
                processedQuantity=processedQuantity,
                batchCode=batchCode,
                txTimestamp=ts_int,
                txTimestampHuman=ts_human,
            )
        except Exception as e:
            print(f"[FarmerProcessingService._parse_processed_event] parse error: {e}")
            return None

    @staticmethod
    def create_processing_requests(farmer_id: str, form) -> Dict[str, Any]:
        """
        Create one or more farmer_request docs from the Processing Request form.

        - One doc per row in the table (Crop ID / Crop Name / Processing Type / Quantity / Price)
        - manufacturer info + common fields shared across all rows
        """
        manufacturer_id = (form.get("manufacturer_id") or "").strip()
        manufacturer_name = (form.get("manufacturer_name") or "").strip()
        request_date = form.get("request_date") or None
        payment_mode = form.get("payment_mode") or None
        note = form.get("note") or ""

        packaging_type = form.get("packaging_type") or None
        bags_count_raw = form.get("bags_count") or "0"
        try:
            bags_count = int(bags_count_raw or 0)
        except ValueError:
            bags_count = 0

        # Table arrays
        crop_ids = form.getlist("items_crop_id[]")
        crop_names = form.getlist("items_crop_name[]")
        proc_types = form.getlist("items_processing_type[]")
        quantities_raw = form.getlist("items_quantity[]")
        prices_raw = form.getlist("items_price[]")

        if not crop_ids:
            return {"ok": False, "error": "No crop rows added to the request."}

        # Try to get manufacturer location from users collection (optional)
        location = ""
        if manufacturer_id:
            mdoc = mongo.db.users.find_one(
                {"manufacturerId": manufacturer_id},
                {"location": 1}
            )
            if not mdoc:
                # fall back to userId, in case that's what you actually store
                mdoc = mongo.db.users.find_one(
                    {"userId": manufacturer_id},
                    {"location": 1}
                )
            if mdoc:
                location = mdoc.get("location") or ""

        docs: List[Dict[str, Any]] = []
        now = datetime.utcnow()

        for idx, crop_id in enumerate(crop_ids):
            crop_id = (crop_id or "").strip()
            if not crop_id:
                continue

            crop_name = (crop_names[idx] if idx < len(crop_names) else "") or ""
            proc_type = (proc_types[idx] if idx < len(proc_types) else "") or ""

            qty_raw = quantities_raw[idx] if idx < len(quantities_raw) else ""
            try:
                harvest_qty = float(qty_raw or 0)
            except ValueError:
                harvest_qty = 0.0

            price_raw = prices_raw[idx] if idx < len(prices_raw) else ""
            try:
                price = float(price_raw or 0)
            except ValueError:
                price = 0.0

            doc = {
                # core schema
                "cropId": crop_id,
                "farmerId": farmer_id,
                "cropType": crop_name,
                "harvestDate": request_date,        # or keep None if you prefer
                "harvestQuantity": harvest_qty,
                "harvesterName": "",                # can be filled later if needed

                "manufacturerId": manufacturer_id,
                "packagingType": packaging_type,
                "status": "pending",

                # RFID / bags
                "rfidEpcs": [],
                "rfidEpc": "",
                "bagQty": bags_count,

                # extra meta
                "processingType": proc_type,
                "price": price,
                "paymentMode": payment_mode,
                "note": note,
                "manufacturerName": manufacturer_name,
                "location": location,

                "created_at": now,
                "updated_at": now,
            }
            docs.append(doc)

        if not docs:
            return {"ok": False, "error": "No valid rows to insert."}

        result = mongo.db.farmer_request.insert_many(docs)
        return {
            "ok": True,
            "inserted_count": len(result.inserted_ids),
            "cropIds": [d["cropId"] for d in docs],
        }

    # -------------------------------------------------
    #  MANUFACTURER / FACTORY INFO PAGE
    # -------------------------------------------------
    @staticmethod
    def get_manufacturer_info(farmer_id: str, manufacturer_id: str) -> Dict[str, Any]:
        """
        Factory / Manufacturer info page:
        - Manufacturer meta from `users` collection
        - All farmer_request docs for this farmer + manufacturer
        """
        from backend.mongo import mongo  # already imported at top, but safe

        # --- 1) Manufacturer document ---
        mdoc = mongo.db.users.find_one(
            {"userId": manufacturer_id}
        ) or mongo.db.users.find_one(
            {"manufacturerId": manufacturer_id}
        ) or mongo.db.users.find_one(
            {"role": "manufacturer", "userId": manufacturer_id}
        )

        # safe defaults
        name = ""
        service_provided = ""
        location = ""
        supports = ""
        owner = ""
        contact = ""

        if mdoc:
            name = mdoc.get("officeName") or mdoc.get("manufacturerName") or ""
            service_provided = (
                mdoc.get("serviceProvided")
                or mdoc.get("services")
                or mdoc.get("service")
                or ""
            )
            # supports may be list or string
            raw_supports = mdoc.get("gstNumber") or mdoc.get("supportedCrops") or ""
            if isinstance(raw_supports, list):
                supports = ", ".join([str(s) for s in raw_supports if s])
            else:
                supports = raw_supports or ""

            location = mdoc.get("location") or ""
            owner = (
                mdoc.get("ownerName")
                or mdoc.get("contactPerson")
                or mdoc.get("managerName")
                or mdoc.get("name")
                or ""
            )
            contact = (
                mdoc.get("phone")
                or mdoc.get("mobile")
                or mdoc.get("contactNumber")
                or ""
            )

        # --- 2) farmer_request docs for this manufacturer + farmer ---
        cur = mongo.db.farmer_request.find(
            {
                "farmerId": farmer_id,
                "manufacturerId": manufacturer_id,
            }
        ).sort([("created_at", -1), ("_id", -1)])

        table_rows: List[Dict[str, Any]] = []
        crops_linked_set = set()
        total_qty = 0.0

        for r in cur:
            crop_id = (r.get("cropId") or "").strip()
            crop_type = (r.get("cropType") or "").strip()
            try:
                qty = float(r.get("harvestQuantity") or 0)
            except Exception:
                qty = 0.0

            status = r.get("status", "pending")

            if crop_type:
                crops_linked_set.add(crop_type)

            total_qty += qty

            table_rows.append(
                {
                    "cropId": crop_id,
                    "cropType": crop_type,
                    "quantity": qty,
                    "status": status,
                }
            )

        crops_linked = ", ".join(sorted(crops_linked_set)) if crops_linked_set else "—"

        factory = {
            "manufacturerId": manufacturer_id,
            "name": name or "—",
            "serviceProvided": service_provided or "—",
            "location": location or "—",
            "supports": supports or "—",
            "owner": owner or "—",
            "contact": contact or "—",
            "cropsLinked": crops_linked,
            "totalQuantity": round(total_qty, 2),
        }

        return {
            "farmerId": farmer_id,
            "manufacturerId": manufacturer_id,
            "factory": factory,
            "items": table_rows,
        }

