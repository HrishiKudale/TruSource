# backend/routes/api_v1.py  (add to your existing file)
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from blockchain_setup import contract, web3
import hashlib

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

# ---------- small helpers ----------
def _ts_to_str(ts):
    try: return datetime.utcfromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
    except: return str(ts)

def _to_int(x):
    try: return int(x)
    except: 
        try: return int(str(x), 10)
        except: return 0

def _decode_event_tuple(t):
    return {
        "status":            t[0],
        "location":          t[1],
        "actor":             t[2],
        "timestamp":         _to_int(t[3]),
        "datePlanted":       t[4],
        "harvestDate":       t[5],
        "receivedDate":      t[6],
        "processedDate":     t[7],
        "packagingType":     t[8],
        "harvesterName":     t[9],
        "harvestQuantity":   _to_int(t[10]),
        "areaSize":          _to_int(t[11]),
        "userId":            t[12],
        "cropId":            t[13],
        "cropType":          t[14],
        "processedQuantity": _to_int(t[15]),
        "batchCode":         t[16],
        # optional t[17], t[18] if your ABI has them (dispatchDate, quantity)
    }

def _event_is_received(ev, user_id):
    return (
        ev.get("status") == "Processed" and
        ev.get("userId") == (user_id or "") and
        not (ev.get("processedDate") or "").strip() and
        ev.get("processedQuantity", 0) == 0 and
        not (ev.get("batchCode") or "").strip()
    )

def _event_is_processed(ev, user_id):
    return (
        ev.get("status") == "Processed" and
        ev.get("userId") == (user_id or "") and
        (
            (ev.get("processedDate") or "").strip() or
            ev.get("processedQuantity", 0) > 0 or
            (ev.get("batchCode") or "").strip()
        )
    )

# ---------- Mongo-backed cache (TTL via expires_at) ----------
def _cache_get(mongo, coll, key):
    doc = mongo.db[coll].find_one({"_id": key})
    if not doc: return None
    if (doc.get("expires_at") or datetime.utcfromtimestamp(0)) < datetime.utcnow():
        return None
    return doc.get("value")

def _cache_put(mongo, coll, key, value, ttl_seconds=300):
    mongo.db[coll].update_one(
        {"_id": key},
        {"$set": {
            "value": value,
            "expires_at": datetime.utcnow() + timedelta(seconds=ttl_seconds),
            "updated_at": datetime.utcnow()
        }},
        upsert=True
    )

def _get_user_crops_cached(user_id):
    from app import mongo
    key = f"user_crops:{user_id}"
    cached = _cache_get(mongo, "api_cache", key)
    if cached is not None:
        return cached
    try:
        ids = contract.functions.getUserCrops(user_id).call() or []
    except Exception:
        ids = []
    # unique, non-empty
    norm = sorted({cid for cid in ids if isinstance(cid, str) and cid.strip()})
    _cache_put(mongo, "api_cache", key, norm, ttl_seconds=120)  # shorter TTL is fine
    return norm

def _get_history_cached(crop_id):
    from app import mongo
    key = f"crop_hist:{crop_id}"
    cached = _cache_get(mongo, "api_cache", key)
    if cached is not None:
        return cached
    try:
        tuples = contract.functions.getCropHistory(crop_id).call() or []
        decoded = [_decode_event_tuple(t) for t in tuples]
    except Exception:
        decoded = []
    _cache_put(mongo, "api_cache", key, decoded, ttl_seconds=300)
    return decoded

# ---------- NEW: one fast endpoint for manufacturer page ----------
@bp.get("/manufacturers/<user_id>/inbox")
def manufacturer_inbox(user_id):
    """
    Returns what the processing UI needs:
      - received_candidates: "Processed" events without processedDate/batch (manufacturer intake)
      - processed_products : "Processed" events with processedDate or batch (finished goods)
    Uses per-crop cached history and concurrent fetch to keep < 1s even with many crops.
    """
    crop_ids = _get_user_crops_cached(user_id)

    received_latest = {}
    processed_latest = {}

    # Fetch histories concurrently (bounded pool)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_get_history_cached, cid): cid for cid in crop_ids}
        for fut in as_completed(futures):
            cid = futures[fut]
            try:
                history = fut.result() or []
            except Exception:
                history = []

            for ev in history:
                if _event_is_processed(ev, user_id):
                    cur = processed_latest.get(ev["cropId"])
                    if (cur is None) or (ev["timestamp"] > cur["timestamp"]):
                        processed_latest[ev["cropId"]] = ev
                elif _event_is_received(ev, user_id):
                    cur = received_latest.get(ev["cropId"])
                    if (cur is None) or (ev["timestamp"] > cur["timestamp"]):
                        received_latest[ev["cropId"]] = ev

    # If a crop is already processed, don’t also show it in received
    for cid in list(received_latest.keys()):
        if cid in processed_latest:
            received_latest.pop(cid, None)

    received_candidates = []
    for cid, ev in received_latest.items():
        received_candidates.append({
            "cropId":          ev.get("cropId", ""),
            "cropType":        ev.get("cropType", "Unknown"),
            "receivedDate":    ev.get("receivedDate", ""),
            "harvestQuantity": ev.get("harvestQuantity", 0),
            "packagingType":   ev.get("packagingType", ""),
            "manufacturerName": ev.get("actor", ""),
        })

    processed_products = []
    for cid, ev in processed_latest.items():
        processed_products.append({
            "cropId":        ev.get("cropId", ""),
            "cropType":      ev.get("cropType", "Unknown"),
            "processedDate": ev.get("processedDate", ""),
            "batchCode":     ev.get("batchCode", ""),
            "processedQuantity": ev.get("processedQuantity", 0),
        })

    received_candidates.sort(key=lambda r: r.get("receivedDate",""), reverse=True)
    processed_products.sort(key=lambda p: p.get("processedDate",""), reverse=True)

    return jsonify(ok=True,
                   user_id=user_id,
                   received_candidates=received_candidates,
                   processed_products=processed_products)
