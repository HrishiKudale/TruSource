# backend/routes/trace_1.py
from __future__ import annotations

from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.routes.consumer_scan import _normalize_for_ui   # you confirmed this path works
from blockchain_setup import contract


bp = Blueprint("trace", __name__)

# ---------- small utils ----------
def _to_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        try:
            return int(str(x), 10)
        except Exception:
            return 0

def _find_cropid_by_batch(batch_code: str) -> Optional[str]:
    from app import mongo
    """
    Resolve batchCode -> cropId using Mongo.
    1) exact match in manufacturer_request
    2) prefix match like BATCHYYYYMMDD-### (choose the latest)
    3) optional RFID mapping fallback (if you saved batchCode there)
    """
    if not batch_code:
        return None

    # exact
    doc = mongo.db.manufacturer_request.find_one(
        {"batchCode": batch_code},
        projection={"cropId": 1, "_id": 0}
    )
    if doc and doc.get("cropId"):
        return doc["cropId"]

    # prefix (accept "BATCH20251001" or "BATCH20251001-003")
    try:
        cand = list(
            mongo.db.manufacturer_request.find(
                {"batchCode": {"$regex": f"^{batch_code}(?:-\\d+)?$"}},
                projection={"cropId": 1, "batchCode": 1, "created_at": 1, "_id": 0}
            ).sort([("created_at", -1)]).limit(1)
        )
        if cand and cand[0].get("cropId"):
            return cand[0]["cropId"]
    except Exception:
        pass

    # RFID mapping fallback (if you used /rfid/map_epc with payload.batchCode)
    try:
        m = mongo.db.rfid_mappings.find_one(
            {"payload.batchCode": batch_code},
            projection={"payload.cropId": 1, "_id": 0}
        )
        if m and m.get("payload", {}).get("cropId"):
            return m["payload"]["cropId"]
    except Exception:
        pass

    return None

def _mongo_fallback_events(crop_id: str) -> List[Dict[str, Any]]:
    from app import mongo
    """
    Build a best-effort timeline from Mongo only (no chain).
    Lets the page render even if chain calls fail/are empty.
    """
    out: List[Dict[str, Any]] = []

    # Farmer request
    fr = mongo.db.farmer_request.find_one({"cropId": crop_id})
    if fr:
        out.append({
            "status": "Planted",
            "stage": "Planted",
            "actor": fr.get("farmerName") or fr.get("farmerId") or "Farmer",
            "location": fr.get("location") or "",
            "timestamp": fr.get("created_at") or "",
            "datePlanted": fr.get("datePlanted") or "",
            "areaSize": _to_int(fr.get("areaSize")),
            "cropType": fr.get("cropType") or "",
            "cropId": crop_id,
            "batchCode": "",
            "image_stage": "planted",
        })
        out.append({
            "status": "Harvested",
            "stage": "Harvested",
            "actor": fr.get("harvesterName") or fr.get("farmerName") or "Farmer",
            "location": fr.get("location") or "",
            "timestamp": fr.get("updated_at") or "",
            "harvestDate": fr.get("harvestDate") or "",
            "harvestQuantity": _to_int(fr.get("harvestQuantity")),
            "packagingType": fr.get("packagingType") or "",
            "cropType": fr.get("cropType") or "",
            "cropId": crop_id,
            "batchCode": "",
            "image_stage": "harvested",
        })

    # Manufacturer received (light record you save on POST /received)
    mr = mongo.db.manufacturer_received.find_one({"cropId": crop_id})
    if mr:
        out.append({
            "status": "Processed",
            "stage": "Received",
            "actor": mr.get("manufacturerName") or "Manufacturer",
            "location": mr.get("manufacturerId") or "",
            "timestamp": mr.get("created_at") or "",
            "receivedDate": mr.get("receivedDate") or "",
            "receivedQuantity": _to_int(mr.get("harvestQuantity")),
            "packagingType": mr.get("packagingType") or "",
            "cropType": mr.get("cropType") or "",
            "cropId": crop_id,
            "batchCode": "",
            "image_stage": "processed_received",
        })

    # Manufacturer processed (where batchCode lives)
    mp = mongo.db.manufacturer_request.find_one({"cropId": crop_id})
    if mp:
        out.append({
            "status": "Processed",
            "stage": "Processed",
            "actor": mp.get("manufacturerName") or "Manufacturer",
            "location": mp.get("manufacturerId") or "",
            "timestamp": mp.get("created_at") or "",
            "processedDate": mp.get("processedDate") or "",
            "processedQuantity": _to_int(mp.get("processedQuantity")),
            "packagingType": mp.get("packagingType") or "",
            "cropType": mp.get("cropType") or "",
            "cropId": crop_id,
            "batchCode": mp.get("batchCode") or "",
            "image_stage": "processed_processed",
        })

    # keep roughly chronological by timestamp string
    out.sort(key=lambda x: str(x.get("timestamp") or ""))
    return out

# ---------- existing batch API (optional, helpful for debugging) ----------
@bp.route("/api/batch_history", methods=["GET"])
def batch_history_api():
    batch = (request.args.get("batch") or "").strip()
    debug = request.args.get("debug") in ("1", "true", "yes")
    if not batch:
        return jsonify(ok=False, err="missing_batch"), 400

    crop_id = _find_cropid_by_batch(batch)
    if not crop_id:
        return jsonify(ok=False, err="unknown_batch", batch=batch), 404

    # Try the chain first
    chain_err = None
    try:
        raw = contract.functions.getCropHistory(crop_id).call()
        events = _normalize_for_ui(raw)
        if not events:
            # Empty on-chain: fill from Mongo so UI still works
            events = _mongo_fallback_events(crop_id)
            return jsonify(ok=True, source="mongo_fallback", batch=batch, crop_id=crop_id,
                           events=events,
                           debug={"note": "chain history empty"} if debug else None), 200
        return jsonify(ok=True, source="chain", batch=batch, crop_id=crop_id,
                       events=events), 200
    except Exception as e:
        chain_err = str(e)
        events = _mongo_fallback_events(crop_id)
        if events:
            return jsonify(ok=True, source="mongo_fallback", batch=batch, crop_id=crop_id,
                           events=events,
                           debug={"chain_error": chain_err} if debug else None), 200
        return jsonify(ok=False, err="chain_error", batch=batch,
                       debug={"chain_error": chain_err} if debug else None), 502

# ---------- PAGE: /track supports crop_id OR batch ----------
@bp.route("/track", methods=["GET"])
def track_page():
    crop_id = (request.args.get("crop_id") or "").strip()
    batch   = (request.args.get("batch") or "").strip()
    debug   = request.args.get("debug") in ("1","true","yes")

    events_combined: List[Dict[str, Any]] = []
    stage_images = None
    product_image_url = None

    # If batch given, resolve to cropId first
    if batch and not crop_id:
        crop_id = _find_cropid_by_batch(batch) or ""

    # With a cropId, try chain; if empty/fail, fall back to Mongo
    if crop_id:
        try:
            raw = contract.functions.getCropHistory(crop_id).call()
            events_combined = _normalize_for_ui(raw)
        except Exception:
            events_combined = []

        if not events_combined:
            events_combined = _mongo_fallback_events(crop_id)

    # Render even if empty; the template shows a friendly “No events” card
    return render_template(
        "track.html",
        crop_id=crop_id,
        events_combined=events_combined,
        stage_images=stage_images,
        product_image_url=product_image_url,
        current_year=datetime.utcnow().year
    )
