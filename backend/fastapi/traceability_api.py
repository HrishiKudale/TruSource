# backend/fastapi/traceability_api.py
# FastAPI API version of backend/routes/trace_1.py
# Uses blockchain data via contract.functions.getCropHistory

import os
from datetime import datetime
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Import the blockchain contract instance
from blockchain_setup import contract

# ==========================================================
# CONFIG
# ==========================================================
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-super-secret")

router = APIRouter(prefix="/api/v1/traceability", tags=["traceability"])

# ==========================================================
# AUTH HELPERS
# ==========================================================
bearer = HTTPBearer(scheme_name="AccessToken", bearerFormat="JWT", auto_error=False)

def _jwt_decode(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"], options={"verify_sub": False})
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def auth_identity(credentials: HTTPAuthorizationCredentials = Security(bearer)) -> Dict[str, Any]:
    if not credentials or (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    payload = _jwt_decode(credentials.credentials.strip())
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Not an access token")

    identity = payload.get("user") or payload.get("sub")
    if isinstance(identity, str):
        identity = {"userId": identity}
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return identity

# ==========================================================
# INTERNAL HELPERS
# ==========================================================

def _ts_to_str(ts: Any) -> str:
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)

def _to_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0

def _normalize_event_tuple(ev: Any) -> Dict[str, Any]:
    n = len(ev)
    if n < 17:
        return {}
    return {
        "status": ev[0],
        "location": ev[1],
        "actor": ev[2],
        "timestamp": _ts_to_str(ev[3]),
        "datePlanted": ev[4],
        "harvestDate": ev[5],
        "receivedDate": ev[6],
        "processedDate": ev[7],
        "packagingType": ev[8],
        "harvesterName": ev[9],
        "harvestQuantity": _to_int(ev[10]),
        "areaSize": _to_int(ev[11]),
        "userId": ev[12],
        "cropId": ev[13],
        "cropType": ev[14],
        "processedQuantity": _to_int(ev[15]),
        "batchCode": ev[16],
        "dispatchDateExt": ev[17] if n >= 19 else None,
        "quantityExt": ev[18] if n >= 19 else None,
    }

def _build_image_stage(status: str, substage: str | None) -> str:
    s = (status or "").strip().lower()
    sub = (substage or "").strip().lower()
    if s in ("processed", "distributed", "retail"):
        if s == "distributed" and sub == "distributed":
            return "distributed_dispatched"
        if sub:
            return f"{s}_{sub}"
    return s or "event"

def _normalize_for_ui(raw: List[Any]) -> List[Dict[str, Any]]:
    from copy import deepcopy
    out: List[Dict[str, Any]] = []

    for tup in raw or []:
        ev = _normalize_event_tuple(tup)
        if not ev:
            continue

        status = ev.get("status") or ""
        location = ev.get("location") or ""
        actor = ev.get("actor") or ""
        ts = ev.get("timestamp") or ""
        crop_id = ev.get("cropId") or ""
        crop_type = ev.get("cropType") or ""
        batch_code = ev.get("batchCode") or ""

        date_planted = ev.get("datePlanted") or ""
        harvest_date = ev.get("harvestDate") or ""
        received_date = ev.get("receivedDate") or ""
        processed_date = ev.get("processedDate") or ""
        packaging_type = ev.get("packagingType") or ""
        harvester_name = ev.get("harvesterName") or ""

        harvest_qty = _to_int(ev.get("harvestQuantity"))
        area_size = _to_int(ev.get("areaSize"))
        processed_qty = _to_int(ev.get("processedQuantity"))

        dispatch_date_ext = ev.get("dispatchDateExt")
        quantity_ext = ev.get("quantityExt")

        has_received = bool(str(received_date).strip())
        has_processed = bool(str(processed_date).strip())
        has_dispatch_e = bool(str(dispatch_date_ext or "").strip())

        q_ext = _to_int(quantity_ext)
        qty_any = q_ext or processed_qty or harvest_qty

        base = {
            "status": status,
            "location": location,
            "actor": actor,
            "timestamp": ts,
            "cropType": crop_type,
            "cropId": crop_id,
            "batchCode": batch_code or "",
        }

        # stage handling
        if status == "Planted":
            out.append({
                **base,
                "stage": "Planted",
                "image_stage": _build_image_stage("planted", None),
                "datePlanted": date_planted,
                "areaSize": area_size,
            })

        elif status == "Harvested":
            out.append({
                **base,
                "stage": "Harvested",
                "image_stage": _build_image_stage("harvested", None),
                "harvestDate": harvest_date,
                "harvestQuantity": harvest_qty,
                "packagingType": packaging_type,
                "harvesterName": harvester_name,
            })

        elif status == "Processed":
            if has_received and not has_processed:
                out.append({
                    **base,
                    "stage": "Received",
                    "image_stage": _build_image_stage("processed", "received"),
                    "receivedDate": received_date,
                    "receivedQuantity": harvest_qty or qty_any,
                })
            else:
                out.append({
                    **base,
                    "stage": "Processed",
                    "image_stage": _build_image_stage("processed", "processed"),
                    "processedDate": processed_date,
                    "processedQuantity": processed_qty or qty_any,
                })

        elif status == "Distributed":
            if has_received and not has_dispatch_e:
                out.append({
                    **base,
                    "stage": "Received",
                    "image_stage": _build_image_stage("distributed", "received"),
                    "receivedDate": received_date,
                    "receivedQuantity": qty_any,
                })
            else:
                out.append({
                    **base,
                    "stage": "Distributed",
                    "image_stage": _build_image_stage("distributed", "distributed"),
                    "dispatchDate": dispatch_date_ext or processed_date,
                    "distributedQuantity": qty_any,
                })

        elif status in ("Retail", "Retailer", "Sold"):
            if has_received and not has_dispatch_e:
                out.append({
                    **base,
                    "stage": "Received",
                    "image_stage": _build_image_stage("retail", "received"),
                    "receivedDate": received_date,
                    "receivedQuantity": qty_any,
                })
            else:
                out.append({
                    **base,
                    "stage": "Sold",
                    "image_stage": _build_image_stage("retail", "sold"),
                    "soldDate": dispatch_date_ext or processed_date,
                    "soldQuantity": qty_any,
                })

        else:
            out.append({
                **base,
                "stage": "Event",
                "image_stage": "event",
                "note": f"Unhandled status '{status}'",
            })

    out.sort(key=lambda r: r.get("timestamp", ""))
    return out

# ==========================================================
# THREADPOOL & CACHE
# ==========================================================
executor = ThreadPoolExecutor(max_workers=5)
crop_history_cache: Dict[str, List[Dict[str, Any]]] = {}

async def fetch_crop_history(crop_id: str) -> List[Dict[str, Any]]:
    # Check cache first
    if crop_id in crop_history_cache:
        return crop_history_cache[crop_id]

    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(executor, contract.functions.getCropHistory(crop_id).call)
    events = _normalize_for_ui(raw)

    # Cache result
    crop_history_cache[crop_id] = events
    return events

# ==========================================================
# ROUTES
# ==========================================================
@router.get("/crop_history")
async def get_crop_history(
    crop_id: str = Query(..., description="Crop ID to fetch blockchain history for"),
    identity: Dict[str, Any] = Depends(auth_identity)
):
    if not crop_id:
        raise HTTPException(status_code=400, detail="Missing crop_id")
    try:
        events = await fetch_crop_history(crop_id)
        return {"ok": True, "crop_id": crop_id, "events": events}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Blockchain error: {e}")

@router.get("/public_crop_history")
async def public_crop_history(crop_id: str = Query(..., description="Crop ID for QR/public lookup")):
    if not crop_id:
        raise HTTPException(status_code=400, detail="Missing crop_id")
    try:
        events = await fetch_crop_history(crop_id)
        return {"ok": True, "crop_id": crop_id, "events": events}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Blockchain error: {e}")

@router.get("/_health")
def trace_health():
    """Health check endpoint"""
    return {"ok": True, "source": "traceability_api", "ts": int(datetime.utcnow().timestamp())}
