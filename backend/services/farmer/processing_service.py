# backend/services/farmer/processing_service.py

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple

from backend.mongo_safe import get_col
from backend.blockchain import get_crop_history
from backend.models.farmer.processing_models import (
    ProcessingRequestModel,
    ProcessingOnchainEvent,
)


class FarmerProcessingService:
    """
    Combines Mongo farmer_request docs with on-chain 'Processed' events
    for farmer processing views.

    IMPORTANT:
    - Never use mongo.db directly here.
    - Always use get_col() so app doesn't crash when Mongo is disabled.
    """

    # -------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------
    @staticmethod
    def get_processing_overview(farmer_id: str) -> Dict[str, Any]:
        """
        Overview is now "1 doc = 1 request", with `items[]` inside each request.

        Returns keys matching ProcessingOverview.html:
        - kpis.total_requests
        - kpis.active_processing
        - kpis.completed_requests
        - kpis.total_processed_qty   (in qtl)
        - items[] rows each with:
            manufacturerId, manufacturerName, location, cropType, totalQuantity, updated_at
        """
        rows: List[Dict[str, Any]] = []

        total_requests = 0
        active_processing = 0
        completed_requests = 0

        total_processed_kg = 0.0  # convert to qtl for KPI

        farmer_req_col = get_col("farmer_request")
        if farmer_req_col is None:
            return {
                "farmerId": farmer_id,
                "kpis": {
                    "total_requests": 0,
                    "active_processing": 0,
                    "completed_requests": 0,
                    "total_processed_qty": 0,  # qtl
                },
                "items": [],
                "error": "Mongo is disabled/unavailable.",
            }

        cursor = (
            farmer_req_col.find(
                {
                    "requestKind": {"$in": ["processing", "Processing"]},
                    "$or": [{"farmerId": farmer_id}, {"farmer_id": farmer_id}],
                }
            )
            .sort([("created_at", -1), ("_id", -1)])
        )

        for raw in cursor:
            total_requests += 1

            manufacturer_id = raw.get("manufacturerId") or raw.get("manufacturer_id") or "—"
            manufacturer_name = raw.get("manufacturerName") or raw.get("manufacturer_name") or "—"
            location = raw.get("location") or "—"
            updated_at = raw.get("updated_at") or raw.get("created_at")

            # NEW STRUCTURE: items[] (list of processing rows)
            items = raw.get("items") if isinstance(raw.get("items"), list) else []

            # Fallback for old docs (single-crop style)
            if not items:
                crop_id = raw.get("cropId") or raw.get("crop_id") or ""
                crop_type = raw.get("cropType") or raw.get("crop_type") or ""
                qty = raw.get("harvestQuantity") or raw.get("harvest_qty") or raw.get("quantity") or 0
                try:
                    qty = float(qty)
                except Exception:
                    qty = 0.0

                if crop_id:
                    items = [{
                        "cropId": crop_id,
                        "cropType": crop_type,
                        "quantityKg": qty,
                        "processingType": raw.get("processingType") or "",
                        "price": raw.get("price") or 0,
                    }]

            # Unique cropIds and cropTypes for this request
            crop_ids: List[str] = []
            crop_types: List[str] = []
            requested_kg = 0.0

            for it in items:
                cid = (it.get("cropId") or it.get("crop_id") or "").strip()
                ctype = (it.get("cropType") or it.get("crop_type") or "").strip()
                qty = it.get("quantityKg") or it.get("harvestQuantity") or it.get("quantity") or 0

                try:
                    qty = float(qty)
                except Exception:
                    qty = 0.0

                if cid and cid not in crop_ids:
                    crop_ids.append(cid)
                if ctype and ctype not in crop_types:
                    crop_types.append(ctype)

                requested_kg += qty

            # Completion logic:
            # Completed request = all cropIds in the request have at least one processed on-chain event.
            processed_kg_for_request = 0.0
            completed_crops = 0

            for cid in crop_ids:
                evt = FarmerProcessingService._latest_processed_event(cid)
                if evt:
                    completed_crops += 1
                    processed_kg_for_request += float(evt.processedQuantity or 0)

            is_completed = (len(crop_ids) > 0 and completed_crops == len(crop_ids))

            if is_completed:
                completed_requests += 1
            else:
                active_processing += 1

            total_processed_kg += processed_kg_for_request

            # Crop label in table (same as your current UX expectation)
            if not crop_types:
                crop_label = "—"
            elif len(crop_types) == 1:
                crop_label = crop_types[0]
            else:
                crop_label = f"{crop_types[0]} +{len(crop_types) - 1}"

            # Total quantity shown in table:
            # if completed -> processed kg, else requested kg
            total_qty_for_row = processed_kg_for_request if is_completed else requested_kg

            rows.append({
                "manufacturerId": manufacturer_id,
                "manufacturerName": manufacturer_name,
                "location": location,
                "cropType": crop_label,
                # IMPORTANT: match template key row.totalQuantity
                "totalQuantity": round(total_qty_for_row, 2),
                "updated_at": updated_at,
                "status": "completed" if is_completed else "active",
                # keep requestId available if you later add a "View Request" link
                "requestId": raw.get("requestId"),
            })

        # KPI in qtl (1 qtl = 100 kg)
        total_processed_qtl = round(total_processed_kg / 100.0, 2)

        return {
            "farmerId": farmer_id,
            "kpis": {
                "total_requests": total_requests,
                "active_processing": active_processing,
                "completed_requests": completed_requests,
                # IMPORTANT: match template key kpis.total_processed_qty
                "total_processed_qty": total_processed_qtl,
            },
            "items": rows,
        }

    # -------------------------------------------------
    # REQUEST DETAIL (NEW, 1 request -> items[])
    # -------------------------------------------------
    @staticmethod
    def get_processing_request_detail(farmer_id: str, request_id: str) -> Dict[str, Any]:
        """
        Returns one request doc (by requestId) and its items[].
        You can render this in a new ProcessingRequestDetail.html later.
        """
        col = get_col("farmer_request")
        if col is None:
            return {"error": "Mongo is disabled/unavailable.", "request": None, "items": [], "grouped": []}

        doc = col.find_one({
            "requestKind": {"$in": ["processing", "Processing"]},
            "$or": [{"farmerId": farmer_id}, {"farmer_id": farmer_id}],
            "requestId": request_id,
        })

        if not doc:
            return {"error": "Request not found.", "request": None, "items": [], "grouped": []}

        items = doc.get("items") if isinstance(doc.get("items"), list) else []

        # Group by crop for UI (same crop split across processing types)
        grouped_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for it in items:
            cid = (it.get("cropId") or "").strip()
            ctype = (it.get("cropType") or "").strip()
            key = (cid, ctype)
            grouped_map.setdefault(key, []).append(it)

        grouped = [{"cropId": k[0], "cropType": k[1], "rows": v} for k, v in grouped_map.items()]

        return {
            "request": {
                "requestId": doc.get("requestId"),
                "manufacturerId": doc.get("manufacturerId") or doc.get("manufacturer_id"),
                "manufacturerName": doc.get("manufacturerName") or doc.get("manufacturer_name"),
                "location": doc.get("location"),
                "requestDate": doc.get("requestDate"),
                "paymentMode": doc.get("paymentMode"),
                "note": doc.get("note"),
                "status": doc.get("status", "pending"),
                "totals": doc.get("totals") or {},
                "updated_at": doc.get("updated_at") or doc.get("created_at"),
            },
            "items": items,
            "grouped": grouped,
        }

    # -------------------------------------------------
    # LEGACY CROP DETAIL (keep for backward compatibility)
    # -------------------------------------------------
    @staticmethod
    def get_processing_detail(farmer_id: str, crop_id: str) -> Dict[str, Any]:
        """
        Old behavior: fetch processing request by cropId.
        Keep this for now if any existing UI links still use /crop/<crop_id>.
        """
        farmer_req_col = get_col("farmer_request")

        req_doc = None
        if farmer_req_col is not None:
            req_doc = farmer_req_col.find_one(
                {
                    "$and": [
                        {"$or": [{"farmerId": farmer_id}, {"farmer_id": farmer_id}]},
                        # either legacy single-crop doc OR request doc that contains this cropId in items[]
                        {
                            "$or": [
                                {"cropId": crop_id},
                                {"crop_id": crop_id},
                                {"items.cropId": crop_id},
                            ]
                        },
                        {"requestKind": {"$in": ["processing", "Processing"]}},
                    ]
                }
            )

        req: Optional[ProcessingRequestModel] = None
        if req_doc:
            # If it is a new request doc with items[], pick the first matching row for the old view
            picked_crop_type = ""
            picked_qty = 0.0

            if isinstance(req_doc.get("items"), list):
                for it in req_doc["items"]:
                    if (it.get("cropId") or "").strip() == crop_id:
                        picked_crop_type = it.get("cropType") or ""
                        try:
                            picked_qty += float(it.get("quantityKg") or 0)
                        except Exception:
                            pass
            else:
                picked_crop_type = req_doc.get("cropType") or req_doc.get("crop_type") or req_doc.get("crop_name") or ""
                try:
                    picked_qty = float(req_doc.get("harvestQuantity") or req_doc.get("harvest_qty") or 0)
                except Exception:
                    picked_qty = 0.0

            try:
                req = ProcessingRequestModel(
                    cropId=crop_id,
                    farmerId=req_doc.get("farmerId") or req_doc.get("farmer_id") or farmer_id,
                    cropType=picked_crop_type,
                    harvestDate=req_doc.get("requestDate") or req_doc.get("harvestDate") or req_doc.get("harvest_date"),
                    harvestQuantity=picked_qty,
                    manufacturerId=req_doc.get("manufacturerId") or req_doc.get("manufacturer_id"),
                    packagingType=req_doc.get("packagingType") or req_doc.get("packaging_type"),
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
        try:
            if not ev or ev[0] != "Processed":
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

    # -------------------------------------------------
    # CREATE PROCESSING REQUEST (1 Mongo doc with items[])
    # -------------------------------------------------
    @staticmethod
    def create_processing_requests(farmer_id: str, form) -> Dict[str, Any]:
        farmer_req_col = get_col("farmer_request")
        users_col = get_col("users")

        if farmer_req_col is None:
            return {"ok": False, "error": "Mongo is disabled/unavailable. Cannot create processing request."}

        manufacturer_id = (form.get("manufacturer_id") or "").strip()
        manufacturer_name = (form.get("manufacturer_name") or "").strip()
        request_date = form.get("request_date") or None
        payment_mode = form.get("payment_mode") or None
        note = form.get("note") or ""

        # ---- Items lists (from hidden inputs in table rows) ----
        crop_ids = form.getlist("items_crop_id[]")
        crop_types = form.getlist("items_crop_type[]")
        proc_types = form.getlist("items_processing_type[]")
        qty_raw_list = form.getlist("items_quantity_kg[]")
        price_raw_list = form.getlist("items_price[]")

        # Backward compatibility (if older JS names still exist)
        if not crop_types:
            crop_types = form.getlist("items_crop_name[]") or form.getlist("items_crop_type[]")
        if not qty_raw_list:
            qty_raw_list = form.getlist("items_quantity[]") or form.getlist("items_quantityKg[]")

        if not crop_ids:
            return {"ok": False, "error": "No crop rows added to the request."}

        # Optional manufacturer location
        location = ""
        if manufacturer_id and users_col is not None:
            mdoc = (
                users_col.find_one({"manufacturerId": manufacturer_id}, {"location": 1})
                or users_col.find_one({"userId": manufacturer_id}, {"location": 1})
            )
            if mdoc:
                location = mdoc.get("location") or ""

        # ---- Build items array ----
        items: List[Dict[str, Any]] = []
        total_qty = 0.0
        total_value = 0.0

        for idx, crop_id in enumerate(crop_ids):
            crop_id = (crop_id or "").strip()
            if not crop_id:
                continue

            crop_type = (crop_types[idx] if idx < len(crop_types) else "") or ""
            proc_type = (proc_types[idx] if idx < len(proc_types) else "") or ""

            qty_raw = (qty_raw_list[idx] if idx < len(qty_raw_list) else "") or "0"
            price_raw = (price_raw_list[idx] if idx < len(price_raw_list) else "") or ""

            try:
                qty = float(qty_raw)
            except Exception:
                qty = 0.0

            try:
                price = float(price_raw) if str(price_raw).strip() != "" else 0.0
            except Exception:
                price = 0.0

            # row-level validation
            if not crop_type or not proc_type or qty <= 0:
                continue

            line_value = round(qty * price, 2) if price > 0 else 0.0

            items.append({
                "cropId": crop_id,
                "cropType": crop_type,
                "processingType": proc_type,
                "quantityKg": qty,
                "price": price,
                "lineValue": line_value,
            })

            total_qty += qty
            total_value += qty * price

        if not items:
            return {"ok": False, "error": "No valid rows found. Please add crop, processing type, and quantity."}

        now = datetime.utcnow()
        request_id = f"PRC{now.strftime('%Y%m%d%H%M%S%f')[:-3]}"

        doc = {
            "requestKind": "processing",
            "requestId": request_id,

            "farmerId": farmer_id,
            "farmer_id": farmer_id,

            "manufacturerId": manufacturer_id,
            "manufacturer_id": manufacturer_id,
            "manufacturerName": manufacturer_name,
            "manufacturer_name": manufacturer_name,

            "requestDate": request_date,
            "paymentMode": payment_mode,
            "note": note,
            "location": location,

            "status": "pending",

            # ✅ all rows here
            "items": items,

            "totals": {
                "totalQuantityKg": round(total_qty, 2),
                "totalValue": round(total_value, 2),
                "itemsCount": len(items),
            },

            "created_at": now,
            "updated_at": now,
        }

        result = farmer_req_col.insert_one(doc)
        return {"ok": True, "requestId": request_id, "mongoId": str(result.inserted_id)}

    # -------------------------------------------------
    # MANUFACTURER / FACTORY INFO PAGE (works with request docs)
    # -------------------------------------------------
    @staticmethod
    def get_manufacturer_info(farmer_id: str, manufacturer_id: str) -> Dict[str, Any]:
        users_col = get_col("users")
        farmer_req_col = get_col("farmer_request")

        if users_col is None or farmer_req_col is None:
            return {
                "farmerId": farmer_id,
                "manufacturerId": manufacturer_id,
                "factory": {
                    "manufacturerId": manufacturer_id,
                    "name": "—",
                    "serviceProvided": "—",
                    "location": "—",
                    "supports": "—",
                    "owner": "—",
                    "contact": "—",
                    "cropsLinked": "—",
                    "totalQuantity": 0,
                },
                "items": [],
                "error": "Mongo is disabled/unavailable.",
            }

        mdoc = (
            users_col.find_one({"userId": manufacturer_id})
            or users_col.find_one({"manufacturerId": manufacturer_id})
            or users_col.find_one({"role": "manufacturer", "userId": manufacturer_id})
        )

        name = ""
        service_provided = ""
        location = ""
        supports = ""
        owner = ""
        contact = ""

        if mdoc:
            name = mdoc.get("officeName") or mdoc.get("manufacturerName") or mdoc.get("name") or ""
            service_provided = mdoc.get("serviceProvided") or mdoc.get("services") or mdoc.get("service") or ""

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
            contact = mdoc.get("phone") or mdoc.get("mobile") or mdoc.get("contactNumber") or ""

        cur = farmer_req_col.find(
            {
                "requestKind": {"$in": ["processing", "Processing"]},
                "$and": [
                    {"$or": [{"farmerId": farmer_id}, {"farmer_id": farmer_id}]},
                    {"$or": [{"manufacturerId": manufacturer_id}, {"manufacturer_id": manufacturer_id}]},
                ],
            }
        ).sort([("created_at", -1), ("_id", -1)])

        table_rows: List[Dict[str, Any]] = []
        crops_linked_set = set()
        total_qty = 0.0

        for r in cur:
            # NEW: request doc with items[]
            items = r.get("items") if isinstance(r.get("items"), list) else []

            if items:
                for it in items:
                    crop_id = (it.get("cropId") or "").strip()
                    crop_type = (it.get("cropType") or "").strip()
                    try:
                        qty = float(it.get("quantityKg") or 0)
                    except Exception:
                        qty = 0.0

                    status = r.get("status", "pending")

                    if crop_type:
                        crops_linked_set.add(crop_type)

                    total_qty += qty
                    table_rows.append({"cropId": crop_id, "cropType": crop_type, "quantity": qty, "status": status})
            else:
                # fallback legacy single-crop doc
                crop_id = (r.get("cropId") or r.get("crop_id") or "").strip()
                crop_type = (r.get("cropType") or r.get("crop_type") or "").strip()
                try:
                    qty = float(r.get("harvestQuantity") or r.get("harvest_qty") or 0)
                except Exception:
                    qty = 0.0

                status = r.get("status", "pending")

                if crop_type:
                    crops_linked_set.add(crop_type)

                total_qty += qty
                table_rows.append({"cropId": crop_id, "cropType": crop_type, "quantity": qty, "status": status})

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



    @staticmethod
    def _status_to_step(status: str, total_steps: int) -> int:
        """
        If you don't store step progress yet, map broad statuses into a step index.
        """
        s = (status or "").strip().lower()
        if total_steps <= 0:
            return 1

        if s in ["pending", "requested"]:
            return 1
        if s in ["approved", "in_progress", "processing"]:
            # middle-ish
            return max(1, min(total_steps, (total_steps // 2) + 1))
        if s in ["processed", "completed", "done"]:
            return total_steps

        return 1

    @staticmethod
    def _build_steps_from_manufacturer(manufacturer_id: str, crop_type: str):
        """
        Builds the stepper list from users.processing_services for that manufacturer + cropType.
        Returns list like: [{"no":1,"title":"Cleaning"}, ...]
        """
        users_col = get_col("users")
        if users_col is None:
            return []

        # Manufacturer can be stored as manufacturerId or userId in your users docs
        mfg = users_col.find_one(
            {
                "role": "manufacturer",
                "$or": [
                    {"manufacturerId": manufacturer_id},
                    {"userId": manufacturer_id},
                ]
            },
            {"_id": 0, "processing_services": 1}
        )

        if not mfg:
            return []

        services = mfg.get("processing_services") or []
        match = None
        for s in services:
            if (s.get("cropType") or "").strip().lower() == (crop_type or "").strip().lower():
                match = s
                break

        if not match:
            return []

        p = (match.get("processingType") or "").strip()
        if not p:
            return []

        # split by comma -> clean
        parts = [x.strip() for x in p.split(",") if x.strip()]

        return [{"no": i + 1, "title": parts[i]} for i in range(len(parts))]

@staticmethod
def get_process_status(farmer_id: str, manufacturer_id: str, crop_id: str):
    col = get_col("farmer_request")
    if col is None:
        return {"ok": False, "error": "Mongo is disabled/unavailable."}

    # Find latest request that contains this cropId for this farmer+manufacturer
    doc = col.find_one(
        {
            "requestKind": {"$in": ["processing", "Processing"]},
            "$or": [{"farmerId": farmer_id}, {"farmer_id": farmer_id}],
            "$or": [{"manufacturerId": manufacturer_id}, {"manufacturer_id": manufacturer_id}],
            "items.cropId": crop_id,
        },
        sort=[("created_at", -1), ("_id", -1)]
    )

    if not doc:
        return {"ok": False, "error": f"No processing request found for crop {crop_id}."}

    items = doc.get("items") if isinstance(doc.get("items"), list) else []
    crop_items = [it for it in items if (it.get("cropId") or "").strip() == crop_id]

    # Quantity (kg) from farmer_request
    total_qty_kg = 0
    for it in crop_items:
        try:
            total_qty_kg += float(it.get("quantityKg") or 0)
        except Exception:
            pass

    # ✅ Processing Type (Crop Details card) must come from farmer_request
    ptypes = [it.get("processingType") for it in crop_items if it.get("processingType")]
    uniq_ptypes = []
    for p in ptypes:
        if p not in uniq_ptypes:
            uniq_ptypes.append(p)
    processing_type_display = " / ".join(uniq_ptypes) if uniq_ptypes else "-"

    # Crop type is needed for manufacturer stepper lookup
    crop_type = crop_items[0].get("cropType") if crop_items else "-"

    status = doc.get("status", "pending")

    # ✅ Steps STRICTLY from users.processing_services
    steps = FarmerProcessingService._build_steps_from_manufacturer(manufacturer_id, crop_type)

    # ✅ Do NOT fallback to farmer_request types for the stepper
    if not steps:
        steps = [{"no": 1, "title": "Processing"}]

    # Progress mapping can still use request status (doesn't affect step definitions)
    current_step = FarmerProcessingService._status_to_step(status, len(steps))

    request_context = {
        "plant_code": manufacturer_id,
        "request_code": crop_id,
        "status": status.capitalize() if isinstance(status, str) else "Pending",

        "request_id": doc.get("requestId", "-"),
        "quantity_sent": f"{int(total_qty_kg)} kg" if total_qty_kg else "-",
        "sent_from": doc.get("location", "Farm / Warehouse") or "Farm / Warehouse",

        # ✅ This is from farmer_request
        "processing_type": processing_type_display,

        "notes": doc.get("note") or "-",

        "started_at": "-",
        "completed_at": "-",
        "processed_batch": "-",
        "output_qty": "-",
    }

    documents_left = [
        {"name": "Inward Receipt", "status": "Not Uploaded"},
        {"name": "Output Report", "status": "Not Uploaded"},
        {"name": "fassi Certificate", "status": "Not Uploaded"},
    ]
    documents_right = [
        {"name": "Processing Sheet", "status": "Not Uploaded"},
        {"name": "Invoice", "status": "Not Uploaded"},
        {"name": "Certificate of origin", "status": "Not Uploaded"},
    ]

    return {
        "ok": True,
        "crop_id": crop_id,
        "crop_type": crop_type,
        "manufacturerId": manufacturer_id,

        # Left card uses this
        "request_context": request_context,

        # Right stepper uses these
        "current_step": current_step,
        "steps": steps,

        "shipment": None,
        "return_shipment": None,
        "documents_left": documents_left,
        "documents_right": documents_right,
    }
