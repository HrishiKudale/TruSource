# farmer_api.py
# FastAPI router that exposes farmer dashboard data for mobile apps.
# Requires: same MongoDB as Flask app + same JWT secret as fastapi_mobile_api.py

import os
import math
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field

from pymongo import MongoClient
import jwt

# top of farmer_api.py (add imports)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


security = HTTPBearer(auto_error=False)


# ======= Config (match your FastAPI app) =======
MONGO_URI      = os.environ.get("MONGO_URI", "mongodb://localhost:27017/crop_traceability_db")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-super-secret")

mongo      = MongoClient(MONGO_URI)
db         = mongo.get_database()
Users      = db["users"]
FarmerReq  = db["farmer_request"]
FarmCoords = db["farm_coordinates"]
Lots       = db["composite_lots"]

router = APIRouter(prefix="/api/v1/farmer", tags=["farmer"])

# ========= Auth helper (must match fastapi_mobile_api.py) =========
# --- add imports ---
from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

# --- one HTTPBearer scheme for this router (docs will show a lock) ---
bearer = HTTPBearer(scheme_name="AccessToken", bearerFormat="JWT", auto_error=False)

def _jwt_decode(token: str) -> Dict[str, Any]:
    try:
        # allow legacy tokens with dict sub
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"], options={"verify_sub": False})
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# <<< REPLACE your old auth_identity(...) with this >>>
def auth_identity(credentials: HTTPAuthorizationCredentials = Security(bearer)) -> Dict[str, Any]:
    if not credentials or (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    payload = _jwt_decode(credentials.credentials.strip())
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Not an access token")

    # prefer new tokens: identity in 'user'; fallback to legacy 'sub'
    identity = payload.get("user")
    if not identity and isinstance(payload.get("sub"), dict):
        identity = payload["sub"]
    if not identity and isinstance(payload.get("sub"), str):
        identity = {"userId": payload["sub"]}

    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return identity



def _require_farmer(identity: Dict[str, Any]) -> str:
    """Ensure role is farmer; return userId."""
    if not identity:
        raise HTTPException(status_code=401, detail="Unauthorized")
    uid = identity.get("userId")
    role = (identity.get("role") or "").lower()
    if role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can access this endpoint")
    if not uid:
        raise HTTPException(status_code=401, detail="Missing userId in token")
    return uid

bearer_scheme = HTTPBearer(auto_error=False)




# ========= Pydantic models =========
class PolygonPoint(BaseModel):
    lat: float
    lng: float

class CompositeComponent(BaseModel):
    supplierFarmerId: str
    cropId: str
    cropType: str
    qtyKg: float = Field(..., gt=0)
    harvestDate: Optional[str] = None
    coaUrl: Optional[str] = None
    invoiceNo: Optional[str] = None
    transportDoc: Optional[str] = None

class CompositePrimary(BaseModel):
    cropId: str
    cropType: str
    harvestDate: Optional[str] = None
    coaUrl: Optional[str] = None

class CompositeCreateRequest(BaseModel):
    manufacturerId: str
    orderRef: Optional[str] = None
    deliveryLocation: Optional[str] = None
    committedQtyKg: float = Field(..., gt=0)
    harvestedQtyKg: float = Field(..., ge=0)
    shortfallKg: Optional[float] = 0
    primary: CompositePrimary
    components: List[CompositeComponent] = []
    reason: Optional[str] = None
    notes: Optional[str] = None

# ========= helpers =========
def _is_valid_id(s: str) -> bool:
    if not s or not isinstance(s, str):
        return False
    s2 = s.strip().upper()
    return len(s2) <= 64 and all(c.isalnum() or c in "-_" for c in s2)

def _pct(part: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 3)

def _approx_area_acres(coords: List[Dict[str, float]]) -> float:
    """Equirectangular-projected polygon area in acres."""
    if not coords or len(coords) < 3:
        return 0.0
    lat0 = float(coords[0].get("lat", 0.0))
    lng0 = float(coords[0].get("lng", 0.0))
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 110540.0

    pts = []
    for p in coords:
        lat = float(p.get("lat", 0.0))
        lng = float(p.get("lng", 0.0))
        x = (lng - lng0) * kx
        y = (lat - lat0) * ky
        pts.append((x,y))
    if pts[0] != pts[-1]:
        pts.append(pts[0])

    s = 0.0
    for i in range(len(pts)-1):
        x1,y1 = pts[i]
        x2,y2 = pts[i+1]
        s += (x1*y2 - x2*y1)
    area_m2 = abs(s) * 0.5
    return area_m2 / 4046.8564224

def _gen_composite_lot_id(now: Optional[datetime] = None) -> str:
    now = now or datetime.utcnow()
    return f"LOT-{now.strftime('%Y%m%d')}"

# ========= data builders =========
def _registered_crops_for_farmer(user_id: str, limit: int) -> List[Dict[str, Any]]:
    """
    Dedup by cropId (case-insensitive), newest-first.
    """
    rows: List[Dict[str, Any]] = []
    seen = set()
    cur = (FarmerReq
           .find({"farmerId": user_id})
           .sort([("created_at", -1), ("_id", -1)])
           .limit(limit * 3))  # over-fetch before dedup
    for r in cur:
        raw_cid = (r.get("cropId") or "").strip()
        norm = raw_cid.upper()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        rows.append({
            "cropId": raw_cid,
            "cropType": r.get("cropType", ""),
            "farmingType": r.get("farmingType", ""),
            "harvestDate": r.get("harvestDate", ""),
            "harvestQuantity": r.get("harvestQuantity", ""),
            "harvesterName": r.get("harvesterName", ""),
            "manufacturerId": r.get("manufacturerId", ""),
            "packagingType": r.get("packagingType", ""),
            "status": r.get("status", "Pending"),
            "created_at": r.get("created_at", None),
        })
        if len(rows) >= limit:
            break
    return rows

def _farmer_requests(user_id: str, limit: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    cur = (FarmerReq
           .find({"farmerId": user_id})
           .sort([("created_at", -1), ("_id", -1)])
           .limit(limit))
    for r in cur:
        rows.append({
            "cropId": r.get("cropId", ""),
            "cropType": r.get("cropType", ""),
            "harvestQuantity": r.get("harvestQuantity", 0),
            "harvestDate": r.get("harvestDate", ""),
            "status": r.get("status", ""),
            "created_at": r.get("created_at", None),
        })
    return rows

def _polygons_and_totals(user_id: str) -> Dict[str, Any]:
    polygons: List[Dict[str, Any]] = []
    total_plots = 0
    total_area_acres = 0.0

    cur = FarmCoords.find({"user_id": user_id})
    for doc in cur:
        crop_id_doc = doc.get("crop_id")
        coords = doc.get("coordinates", [])
        crop_type_mongo = doc.get("cropType")
        area_size = doc.get("area_size")
        date_planted = doc.get("date_planted")

        slug = (crop_type_mongo or "crop").lower().replace(" ", "_")
        image_url = f"/static/images/crops/{slug}.jpg"
        placeholder = "https://images.unsplash.com/photo-1501004318641-b39e6451bec6?w=900&q=70&auto=format"

        polygons.append({
            "cropId": crop_id_doc,
            "cropType": crop_type_mongo,
            "coordinates": coords,
            "imageUrl": image_url,
            "placeholderUrl": placeholder,
            "area_size": area_size or "",
            "date_planted": date_planted or "",
        })

        # area
        parsed = None
        if isinstance(area_size, (int, float)):
            parsed = float(area_size)
        elif isinstance(area_size, str):
            try:
                parsed = float(area_size.split()[0])
            except Exception:
                parsed = None
        if parsed is not None:
            total_area_acres += parsed
        else:
            total_area_acres += _approx_area_acres(coords)

    total_plots = len(polygons)
    total_area_acres = round(total_area_acres, 2)
    return {"polygons": polygons, "total_plots": total_plots, "total_area_acres": total_area_acres}

# ========= Routes =========

@router.get("/overview")
def farmer_overview(
    limit: int = Query(20, ge=1, le=200),
    identity: Dict[str, Any] = Depends(auth_identity)
):
    """
    Mobile-friendly aggregate for Farmer dashboard.
    Returns:
      - registered_crops (dedup, newest-first)
      - farmer_requests (for harvest charts)
      - polygons + totals (area, plots)
    """
    user_id = _require_farmer(identity)
    reg  = _registered_crops_for_farmer(user_id, limit)
    reqs = _farmer_requests(user_id, limit)
    poly = _polygons_and_totals(user_id)
    return {
        "ok": True,
        "userId": user_id,
        "registered_crops": reg,
        "farmer_requests": reqs,
        **poly
    }

@router.get("/crops")
def farmer_crops(
    limit: int = Query(50, ge=1, le=200),
    identity: Dict[str, Any] = Depends(auth_identity)
):
    user_id = _require_farmer(identity)
    return {"ok": True, "items": _registered_crops_for_farmer(user_id, limit)}

@router.get("/requests")
def farmer_requests_list(
    limit: int = Query(100, ge=1, le=500),
    identity: Dict[str, Any] = Depends(auth_identity)
):
    user_id = _require_farmer(identity)
    return {"ok": True, "items": _farmer_requests(user_id, limit)}

@router.get("/polygons")
def farmer_polygons(identity: Dict[str, Any] = Depends(auth_identity)):
    user_id = _require_farmer(identity)
    return {"ok": True, **_polygons_and_totals(user_id)}

# ---------- Composite Lot (Create / List) ----------
@router.post("/lots/composite")
def composite_lot_create(
    payload: CompositeCreateRequest,
    identity: Dict[str, Any] = Depends(auth_identity)
):
    user_id = _require_farmer(identity)

    # Validate IDs
    if not _is_valid_id(payload.manufacturerId):
        raise HTTPException(status_code=400, detail="invalid manufacturerId")
    if not _is_valid_id(payload.primary.cropId):
        raise HTTPException(status_code=400, detail="invalid primary.cropId")
    if not payload.primary.cropType:
        raise HTTPException(status_code=400, detail="invalid primary.cropType")

    # Components validation
    components: List[Dict[str, Any]] = []
    for i, c in enumerate(payload.components):
        if not _is_valid_id(c.supplierFarmerId):
            raise HTTPException(status_code=400, detail=f"components[{i}].supplierFarmerId_invalid")
        if not _is_valid_id(c.cropId):
            raise HTTPException(status_code=400, detail=f"components[{i}].cropId_invalid")
        if not c.cropType:
            raise HTTPException(status_code=400, detail=f"components[{i}].cropType_invalid")
        components.append({
            "supplierFarmerId": c.supplierFarmerId,
            "cropId": c.cropId,
            "cropType": c.cropType,
            "harvestDate": c.harvestDate,
            "qtyKg": round(c.qtyKg, 3),
            "coaUrl": c.coaUrl,
            "invoiceNo": c.invoiceNo,
            "transportDoc": c.transportDoc
        })

    # Quantities
    committed = round(payload.committedQtyKg, 3)
    harvested = round(payload.harvestedQtyKg, 3)
    shortfall_client = round(payload.shortfallKg or 0.0, 3)
    shortfall_calc = max(0.0, committed - harvested)
    topup_sum = round(sum(c["qtyKg"] for c in components), 3)
    total_qty = round(harvested + topup_sum, 3)

    # Composition vector
    composition: List[Dict[str, Any]] = []
    if harvested > 0:
        composition.append({
            "label": f"You {payload.primary.cropId}",
            "farmerId": user_id,
            "sourceType": "primary",
            "cropId": payload.primary.cropId,
            "cropType": payload.primary.cropType,
            "qtyKg": harvested,
            "pct": _pct(harvested, total_qty)
        })
    for c in components:
        composition.append({
            "label": f"{c['supplierFarmerId']} • {c['cropId']}",
            "farmerId": c["supplierFarmerId"],
            "sourceType": "component",
            "cropId": c["cropId"],
            "cropType": c["cropType"],
            "qtyKg": c["qtyKg"],
            "pct": _pct(c["qtyKg"], total_qty)
        })

    now = datetime.utcnow()
    lot_id = _gen_composite_lot_id(now)

    doc = {
        "compositeLotId": lot_id,
        "farmerId": user_id,
        "manufacturerId": payload.manufacturerId,
        "orderRef": payload.orderRef or None,
        "deliveryLocation": payload.deliveryLocation or None,

        "committedQtyKg": committed,
        "harvestedQtyKg": harvested,
        "shortfallClientKg": shortfall_client,
        "shortfallCalcKg": shortfall_calc,
        "totalQtyKg": total_qty,

        "primary": {
            "cropId": payload.primary.cropId,
            "cropType": payload.primary.cropType,
            "harvestDate": payload.primary.harvestDate,
            "coaUrl": payload.primary.coaUrl
        },
        "components": components,
        "composition": composition,

        "reason": payload.reason or None,
        "notes": payload.notes or None,

        "status": "Created",
        "created_at": now
    }

    try:
        Lots.insert_one(doc)
    except Exception:
        raise HTTPException(status_code=500, detail="db_write_failed")

    return {"ok": True, "compositeLotId": lot_id}

@router.get("/lots/composite")
def composite_lot_list(
    limit: int = Query(50, ge=1, le=200),
    identity: Dict[str, Any] = Depends(auth_identity)
):
    user_id = _require_farmer(identity)
    items: List[Dict[str, Any]] = []
    cur = (Lots.find({"farmerId": user_id})
               .sort([("created_at", -1), ("_id", -1)])
               .limit(limit))
    for d in cur:
        d["_id"] = str(d.get("_id"))
        items.append(d)
    return {"ok": True, "items": items}

# ---------- Recall notifications (farmer) ----------
@router.get("/recall/notifications")
def farmer_recall_notifications(
    span: int = Query(2_000_000, ge=0),
    fromBlock: Optional[int] = Query(None),
    toBlock: Optional[int]   = Query(None),
    identity: Dict[str, Any] = Depends(auth_identity)
):
    """
    
    JSON equivalent of your Flask GET /api/recall/notifications/farmer
    This implementation expects your existing manufacturer scanner utility to be exposed separately,
    so here we return a stable empty list if not integrated yet.
    Hook your on-chain scanner here if desired.
    """
    user_id = _require_farmer(identity)
    # TODO: integrate your _scan_recall_events_for_user(user_id, span, fromBlock, toBlock)
    # For now we return an OK/empty payload (safe default).
    return {"ok": True, "items": []}

# ---------- Register Crop (FastAPI port of Flask register_crop.py) ----------

# Optional: try to import your chain helpers. If missing, the /register endpoint will 501.
try:
    from blockchain_setup import contract, web3, account, suggest_fees  # type: ignore
    _CHAIN_READY = True
except Exception:
    _CHAIN_READY = False

# ----- ID helpers: keep CROP### format -----
def _parse_crop_suffix(crop_id: str) -> int:
    if not crop_id or not isinstance(crop_id, str) or not crop_id.upper().startswith("CROP"):
        return 0
    try:
        return int(crop_id[4:])
    except Exception:
        return 0

def _format_crop_id(seq: int) -> str:
    if seq < 1:
        seq = 1
    return f"CROP{seq:03d}"

def _next_crop_id_from_mongo(user_id: str) -> str:
    max_num = 0
    try:
        # Only read crop_id field for this user
        cur = FarmCoords.find({"user_id": user_id}, {"crop_id": 1})
        for d in cur:
            n = _parse_crop_suffix(d.get("crop_id", ""))
            if n > max_num:
                max_num = n
    except Exception:
        # safe fallback
        return "CROP001"
    return _format_crop_id(max_num + 1)

# ----- Pydantic payloads -----
class CoordinatesPoint(BaseModel):
    lat: float
    lng: float

class SaveCoordinatesRequest(BaseModel):
    cropId: str = Field(..., min_length=5)           # e.g. CROP001
    cropType: Optional[str] = None
    datePlanted: Optional[str] = None               # keep as string (ISO or yyyy-mm-dd)
    areaSize: Optional[float] = None                # in acres (client-side units)
    coordinates: List[CoordinatesPoint]
    location: Optional[str] = None                  # free-form string

class RegisterCropRequest(BaseModel):
    cropId: str
    cropType: str
    farmerName: str
    datePlanted: str
    farmingType: str
    seedType: str
    location: str
    areaSize: float                                  # will be rounded and cast to int

# ----- Utility (chain) -----
def _raw_tx_bytes(signed) -> Optional[bytes]:
    return getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction", None)

# GET: next crop id for this farmer
@router.get("/crops/next-id")
def farmer_next_crop_id(identity: Dict[str, Any] = Depends(auth_identity)):
    user_id = _require_farmer(identity)
    return {"ok": True, "nextCropId": _next_crop_id_from_mongo(user_id)}

# POST: save farm coordinates to Mongo (mirrors Flask save_farm_coordinates)
@router.post("/crops/coordinates")
def farmer_save_coordinates(payload: SaveCoordinatesRequest, identity: Dict[str, Any] = Depends(auth_identity)):
    user_id = _require_farmer(identity)

    if not payload.coordinates or len(payload.coordinates) < 3:
        raise HTTPException(status_code=400, detail="coordinates must contain at least 3 points")

    doc = {
        "user_id": user_id,
        "crop_id": payload.cropId,
        "cropType": payload.cropType,
        "area_size": str(payload.areaSize) if payload.areaSize is not None else None,
        "date_planted": payload.datePlanted,
        "coordinates": [p.dict() for p in payload.coordinates],
        "location": payload.location,
        "created_at": datetime.utcnow(),
    }

    try:
        FarmCoords.insert_one(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"mongo_insert_failed: {e}")

    return {"ok": True, "saved": {"cropId": payload.cropId}}

# POST: register crop on-chain (optional; requires blockchain_setup.py)
@router.post("/crops/register")
def farmer_register_crop(payload: RegisterCropRequest, identity: Dict[str, Any] = Depends(auth_identity)):
    user_id = _require_farmer(identity)

    if not _CHAIN_READY:
        # You can swap to 400 if you prefer
        raise HTTPException(status_code=501, detail="blockchain_setup not available on server")

    # Convert to int acres like Flask did (round then cast)
    try:
        area_size_int = int(round(float(payload.areaSize)))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid areaSize")

    try:
        fn = contract.functions.registerCrop(
            user_id,
            payload.cropId.strip(),
            payload.cropType.strip(),
            payload.farmerName.strip(),
            payload.datePlanted.strip(),
            payload.farmingType.strip(),
            payload.seedType.strip(),
            payload.location.strip(),
            area_size_int
        )

        gas_est = fn.estimate_gas({'from': account.address})
        prio, max_fee = suggest_fees()

        txn = fn.build_transaction({
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address, "pending"),
            'chainId': 80002,  # Polygon Amoy
            'gas': int(gas_est * 1.20),
            'maxPriorityFeePerGas': prio,
            'maxFeePerGas': max_fee,
        })

        signed = account.sign_transaction(txn)
        raw = _raw_tx_bytes(signed)
        if raw is None:
            raise HTTPException(status_code=500, detail="unable_to_read_signed_raw_tx")

        tx_hash = web3.eth.send_raw_transaction(raw)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

        if not receipt or receipt.status != 1:
            raise HTTPException(status_code=500, detail="onchain_register_failed")

        # Optional read-back (safe-guarded)
        try:
            crop = contract.functions.getCrop(payload.cropId.strip()).call()
            area_size_onchain = crop[8] if len(crop) > 8 else area_size_int
        except Exception:
            area_size_onchain = area_size_int

        return {
            "ok": True,
            "txHash": tx_hash.hex(),
            "cropId": payload.cropId,
            "areaSize": area_size_onchain
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"register_crop_exception: {e}")

# ---------- Record Harvest (FastAPI port of backend/routes/record_harvest.py) ----------

import re, json, time, base64, hashlib, hmac
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Optional: qr generator (if present)
try:
    from qr_generator import generate_qr_code  # type: ignore
    _QR_READY = True
except Exception:
    _QR_READY = False

# Reuse chain helpers loaded earlier for /crops/register
# _CHAIN_READY, contract, web3, account, suggest_fees are already defined above.

# Collections used here
CropCache   = db["crop_cache"]
RfidPlans   = db["rfid_write_plans"]
RfidEvents  = db["rfid_write_events"]

# ----------------- EPC helpers -----------------
EPC_EXPECTED_HEX_LEN = int(os.environ.get("RFID_EPC_HEX_LEN", "24"))

def _epc_normalize_wedge(s: str) -> str:
    """Normalize wedge to HEX (truncate to EPC_EXPECTED_HEX_LEN)."""
    if not s:
        return ""
    s = re.sub(r'[^0-9a-fA-F]', '', s).upper()
    if EPC_EXPECTED_HEX_LEN > 0:
        s = s[:EPC_EXPECTED_HEX_LEN]
    return s

def _epc_clean_code(s: str) -> str:
    """Clean manual codes like 'EPC0001' (A–Z/0–9, <=32)."""
    if not s:
        return ""
    return re.sub(r'[^0-9A-Z]', '', s.upper())[:32]

def _int_or(v, d=0):
    try:
        return int(round(float(v)))
    except Exception:
        return d

# ----------------- cache helpers -----------------
def _now_ts() -> int:
    return int(time.time())

_MAX_FETCH_SECONDS   = float(os.environ.get("CROP_LIST_BUDGET_SECONDS", "3.0"))
_MAX_WORKERS         = int(os.environ.get("CROP_LIST_MAX_WORKERS", "16"))
_CACHE_TTL_SECONDS   = int(os.environ.get("CROP_LIST_CACHE_TTL_SECONDS", "300"))  # 5 min

def _cache_get_harvest_flag(crop_id: str):
    """Return (known, is_harvested) using a small Mongo cache."""
    try:
        doc = CropCache.find_one({"cropId": crop_id}, {"harvestDate": 1, "updated_at": 1})
        if not doc:
            return (False, None)
        updated_at = doc.get("updated_at")
        if not isinstance(updated_at, (int, float)) or (_now_ts() - updated_at > _CACHE_TTL_SECONDS):
            return (False, None)
        return (True, bool(doc.get("harvestDate")))
    except Exception:
        return (False, None)

def _cache_put_harvest(crop_id: str, harvest_date: str):
    try:
        CropCache.update_one(
            {"cropId": crop_id},
            {"$set": {"harvestDate": harvest_date or "", "updated_at": _now_ts()},
             "$setOnInsert": {"created_at": _now_ts()}},
            upsert=True
        )
    except Exception:
        pass

def _get_user_unharvested_crops_fast(user_id: str) -> list:
    """
    Return crops for user where harvestDate == "".
    Uses caching + parallel eth_call and enforces ~3s budget.
    """
    if not _CHAIN_READY:
        # Without chain, we cannot verify harvest status; return empty safely.
        return []

    # Step 1: all cropIds (dedup)
    try:
        all_crops_list = contract.functions.getUserCrops(user_id).call()
    except Exception:
        return []

    seen = set()
    unique = []
    for cid in reversed(all_crops_list or []):
        if cid and cid not in seen:
            seen.add(cid)
            unique.append(cid)
    unique.reverse()

    # Step 2: cache split
    unharvested, to_fetch = [], []
    for cid in unique:
        known, is_h = _cache_get_harvest_flag(cid)
        if known:
            if not is_h:
                unharvested.append(cid)
        else:
            to_fetch.append(cid)

    if not to_fetch:
        return unharvested

    # Step 3: fetch details in parallel within budget
    started = time.time()
    budget = max(0.4, _MAX_FETCH_SECONDS)
    def remaining(): return max(0.0, budget - (time.time() - started))

    def _fetch_one(cid: str):
        try:
            # getCrop returns (..., datePlanted, harvestDate, areaSize); harvestDate index 7
            details = contract.functions.getCrop(cid).call()
            hdt = details[7] if isinstance(details, (list, tuple)) and len(details) > 7 else ""
            _cache_put_harvest(cid, hdt or "")
            return (cid, hdt)
        except Exception:
            return (cid, None)

    workers = min(len(to_fetch), max(1, _MAX_WORKERS))
    results = []

    BATCH = 64
    for i in range(0, len(to_fetch), BATCH):
        if remaining() <= 0:
            break
        batch = to_fetch[i:i+BATCH]
        with ThreadPoolExecutor(max_workers=min(workers, len(batch))) as ex:
            futs = {ex.submit(_fetch_one, cid): cid for cid in batch}
            try:
                for fut in as_completed(futs, timeout=remaining()):
                    results.append(fut.result())
            except Exception:
                pass

    for (cid, hdt) in results:
        if hdt == "":              # empty → not harvested yet
            unharvested.append(cid)

    unharvested_set = set(unharvested)
    return [cid for cid in unique if cid in unharvested_set]

# ------------- DTOs -------------
class HarvestSaveRequest(BaseModel):
    cropId: str
    cropType: Optional[str] = ""
    farmingType: Optional[str] = ""
    harvestDate: Optional[str] = ""
    harvesterName: Optional[str] = ""
    harvestQuantity: Optional[float] = None
    packagingType: Optional[str] = ""
    manufacturerId: Optional[str] = ""
    rfidEpc: Optional[str] = ""          # legacy single EPC (not bag scan)
    bagQty: Optional[int] = None         # expected number of bags (optional)

class HarvestRecordRequest(BaseModel):
    cropId: str
    harvestDate: str
    harvesterName: str
    harvestQuantity: int
    packagingType: str
    manufacturerId: str
    cropType: Optional[str] = ""         # helpful for QR
    rfidEpc: Optional[str] = ""          # legacy single EPC (optional)
    bagQty: Optional[int] = None

class BagAddRequest(BaseModel):
    cropId: str
    epc: str
    bagQty: Optional[int] = 0

# ------------- Routes -------------

@router.get("/crops/unharvested")
def farmer_unharvested(identity: Dict[str, Any] = Depends(auth_identity)):
    user_id = _require_farmer(identity)
    return {"ok": True, "items": _get_user_unharvested_crops_fast(user_id)}

@router.post("/harvest/save")
def harvest_save(payload: HarvestSaveRequest, identity: Dict[str, Any] = Depends(auth_identity)):
    """
    Mongo-only save/update. No chain TX.
    """
    user_id = _require_farmer(identity)

    crop_id = (payload.cropId or "").strip()
    if not crop_id:
        raise HTTPException(status_code=400, detail="missing cropId")

    harvest_qty = payload.harvestQuantity
    if harvest_qty not in (None, ""):
        try:
            harvest_qty = int(round(float(harvest_qty)))
        except Exception:
            raise HTTPException(status_code=400, detail="bad_harvestQuantity")

    # Clean legacy EPC; do not let it collide with other docs
    rfid_epc = _epc_normalize_wedge(payload.rfidEpc or "")
    if rfid_epc:
        other = FarmerReq.find_one({
            "$and": [
                {"$or": [{"rfidEpcs.epc": rfid_epc}, {"rfidEpc": rfid_epc}]},
                {"$or": [{"cropId": {"$ne": crop_id}}, {"farmerId": {"$ne": user_id}}]}
            ]
        }, {"_id": 1})
        if other:
            rfid_epc = ""

    doc = {
        "farmerId":        user_id,
        "cropId":          crop_id,
        "cropType":        payload.cropType or "",
        "farmingType":     payload.farmingType or "",
        "harvestDate":     payload.harvestDate or "",
        "harvesterName":   payload.harvesterName or "",
        "harvestQuantity": harvest_qty,
        "packagingType":   payload.packagingType or "",
        "manufacturerId":  payload.manufacturerId or "",
        "rfidEpc":         rfid_epc,
        "status":          "Pending",
        "updated_at":      datetime.utcnow(),
    }
    if payload.bagQty is not None:
        doc["bagQty"] = int(payload.bagQty)

    FarmerReq.update_one(
        {"farmerId": user_id, "cropId": crop_id},
        {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow(), "rfidEpcs": []}},
        upsert=True
    )

    return {"ok": True, "cropId": crop_id}

@router.post("/harvest/record")
def harvest_record(payload: HarvestRecordRequest, identity: Dict[str, Any] = Depends(auth_identity)):
    """
    Chain TX registerHarvest + Mongo upsert + optional QR.
    """
    user_id = _require_farmer(identity)

    if not _CHAIN_READY:
        raise HTTPException(status_code=501, detail="blockchain_setup not available on server")

    crop_id = payload.cropId.strip()
    try:
        hq = int(round(float(payload.harvestQuantity)))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid harvestQuantity")

    # Legacy EPC collision avoidance
    rfid_epc_single = _epc_normalize_wedge(payload.rfidEpc or "")
    if rfid_epc_single:
        other = FarmerReq.find_one({
            "$and": [
                {"$or": [{"rfidEpcs.epc": rfid_epc_single}, {"rfidEpc": rfid_epc_single}]},
                {"$or": [{"cropId": {"$ne": crop_id}}, {"farmerId": {"$ne": user_id}}]}
            ]
        }, {"_id": 1})
        if other:
            rfid_epc_single = ""

    try:
        fn = contract.functions.registerHarvest(
            user_id, crop_id, payload.harvestDate.strip(),
            payload.harvesterName.strip(), hq, payload.packagingType.strip()
        )
        gas_est = fn.estimate_gas({'from': account.address})
        prio, max_fee = suggest_fees()
        txn = fn.build_transaction({
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address, "pending"),
            'chainId': 80002,
            'gas': int(gas_est * 1.20),
            'maxPriorityFeePerGas': prio,
            'maxFeePerGas': max_fee,
        })
        signed  = account.sign_transaction(txn)
        raw_tx  = getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction", None)
        if not raw_tx:
            raise HTTPException(status_code=500, detail="unable_to_read_signed_raw_tx")
        tx_hash = web3.eth.send_raw_transaction(raw_tx)
        web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

        # Upsert request doc
        request_data = {
            "cropId": crop_id,
            "cropType": payload.cropType or "",
            "harvestDate": payload.harvestDate,
            "harvesterName": payload.harvesterName,
            "harvestQuantity": hq,
            "packagingType": payload.packagingType,
            "manufacturerId": payload.manufacturerId,
            "farmerId": user_id,
            "rfidEpc": rfid_epc_single,
            "rfidEpcs": [],
            "bagQty": payload.bagQty,
            "status": "Pending",
        }
        FarmerReq.update_one(
            {"farmerId": user_id, "cropId": crop_id},
            {"$set": request_data, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )

        # Generate QR (optional)
        qr_png = None
        if _QR_READY:
            try:
                qr_payload = {
                    "cropId": crop_id,
                    "cropType": payload.cropType or "",
                    "harvestDate": payload.harvestDate,
                    "harvesterName": payload.harvesterName,
                    "harvestQuantity": hq,
                    "packagingType": payload.packagingType,
                    "manufacturerId": payload.manufacturerId,
                    "farmerId": user_id,
                    "rfidEpc": rfid_epc_single,
                    "txHash": tx_hash.hex()
                }
                qr_path = f"static/qrcodes/{crop_id}_harvest.png"
                generate_qr_code(qr_payload, qr_path)
                qr_png = "/" + qr_path
            except Exception:
                qr_png = None

        # Cache: mark this crop harvested
        try:
            _cache_put_harvest(crop_id, payload.harvestDate or "1")
        except Exception:
            pass

        return {
            "ok": True,
            "txHash": tx_hash.hex(),
            "cropId": crop_id,
            "qr": qr_png
        }

    except HTTPException:
        raise
    except Exception as e:
        # fallback: still persist so user doesn't lose work
        try:
            FarmerReq.update_one(
                {"farmerId": user_id, "cropId": crop_id},
                {"$set": {
                    "cropId": crop_id,
                    "cropType": payload.cropType or "",
                    "harvestDate": payload.harvestDate,
                    "harvesterName": payload.harvesterName,
                    "harvestQuantity": hq,
                    "packagingType": payload.packagingType,
                    "manufacturerId": payload.manufacturerId,
                    "farmerId": user_id,
                    "rfidEpc": rfid_epc_single,
                    "status": "Pending (offline)",
                    "updated_at": datetime.utcnow(),
                }, "$setOnInsert": {"rfidEpcs": [], "created_at": datetime.utcnow()}},
                upsert=True
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"registerHarvest_exception: {e}")

@router.get("/harvest/bags")
def harvest_bags_list(cropId: str = Query(..., min_length=5), identity: Dict[str, Any] = Depends(auth_identity)):
    user_id = _require_farmer(identity)
    FarmerReq.create_index([("farmerId", 1), ("cropId", 1)])
    FarmerReq.create_index([("rfidEpcs.epc", 1)])
    FarmerReq.create_index([("rfidEpc", 1)])

    doc = FarmerReq.find_one({"farmerId": user_id, "cropId": cropId}) or {}
    items = [{"epc": d.get("epc"), "bagQty": d.get("bagQty", 0)} for d in (doc.get("rfidEpcs") or [])]
    return {"ok": True, "items": items, "count": len(items)}

@router.post("/harvest/bag-add")
def harvest_bag_add(payload: BagAddRequest, identity: Dict[str, Any] = Depends(auth_identity)):
    user_id = _require_farmer(identity)
    crop_id = (payload.cropId or "").strip()
    if not crop_id:
        raise HTTPException(status_code=400, detail="cropId required")

    raw = (payload.epc or "").strip()
    epc = _epc_clean_code(raw)
    if len(epc) < 4:
        epc = _epc_normalize_wedge(raw)
    if not epc:
        raise HTTPException(status_code=400, detail="bad_epc")

    bag_qty = _int_or(payload.bagQty or 0, 0)

    FarmerReq.update_one(
        {"farmerId": user_id, "cropId": crop_id},
        {"$setOnInsert": {"created_at": datetime.utcnow(), "rfidEpcs": []}},
        upsert=True
    )

    # reject duplicate anywhere else
    other = FarmerReq.find_one({
        "$and": [
            {"$or": [{"rfidEpcs.epc": epc}, {"rfidEpc": epc}]},
            {"$or": [{"cropId": {"$ne": crop_id}}, {"farmerId": {"$ne": user_id}}]}
        ]
    }, {"_id": 1})
    if other:
        raise HTTPException(status_code=409, detail="epc_already_used_in_another_request")

    # reject duplicate in this doc
    doc = FarmerReq.find_one({"farmerId": user_id, "cropId": crop_id}, {"rfidEpcs": 1}) or {}
    if any((it or {}).get("epc") == epc for it in (doc.get("rfidEpcs") or [])):
        raise HTTPException(status_code=409, detail="epc_already_scanned")

    # push
    FarmerReq.update_one(
        {"farmerId": user_id, "cropId": crop_id},
        {"$push": {"rfidEpcs": {"epc": epc, "bagQty": bag_qty, "added_at": datetime.utcnow()}},
         "$set": {"updated_at": datetime.utcnow()}}
    )

    # set legacy first-epc if empty
    doc2 = FarmerReq.find_one({"farmerId": user_id, "cropId": crop_id}, {"rfidEpc": 1, "rfidEpcs": 1}) or {}
    if not (doc2.get("rfidEpc") or ""):
        first_epc = (doc2.get("rfidEpcs") or [{}])[0].get("epc", "")
        if first_epc:
            FarmerReq.update_one({"farmerId": user_id, "cropId": crop_id}, {"$set": {"rfidEpc": first_epc}})

    # recompute scanned count
    doc3 = FarmerReq.find_one({"farmerId": user_id, "cropId": crop_id}, {"rfidEpcs": 1}) or {}
    scanned = len(doc3.get("rfidEpcs") or [])
    FarmerReq.update_one({"farmerId": user_id, "cropId": crop_id}, {"$set": {"bagQty": scanned}})

    return {"ok": True, "epc": epc, "scanned": scanned}

@router.delete("/harvest/bag-delete")
def harvest_bag_delete(cropId: str = Query(...), epc: str = Query(...), identity: Dict[str, Any] = Depends(auth_identity)):
    user_id = _require_farmer(identity)

    raw = (epc or "").strip()
    cleaned = _epc_clean_code(raw)
    if len(cleaned) < 4:
        cleaned = _epc_normalize_wedge(raw)
    if not cleaned:
        raise HTTPException(status_code=400, detail="bad_epc")

    FarmerReq.update_one(
        {"farmerId": user_id, "cropId": cropId},
        {"$pull": {"rfidEpcs": {"epc": cleaned}}, "$set": {"updated_at": datetime.utcnow()}}
    )

    doc = FarmerReq.find_one({"farmerId": user_id, "cropId": cropId}) or {}
    scanned = len(doc.get("rfidEpcs") or [])
    FarmerReq.update_one({"farmerId": user_id, "cropId": cropId}, {"$set": {"bagQty": scanned}})

    return {"ok": True, "removed": True, "scanned": scanned}

# --- Compact tag payload + optional ESP32 write bridge ---

def _compact_harvest_doc_to_tag(doc: dict, secret: Optional[str] = None) -> str:
    hqt = doc.get("harvestQuantity", "")
    try:
        if hqt not in ("", None):
            hqt = int(round(float(hqt)))
    except Exception:
        hqt = ""

    payload = {
        "cid": doc.get("cropId", ""),
        "ctp": doc.get("cropType", ""),
        "hdt": doc.get("harvestDate", ""),
        "hnm": doc.get("harvesterName", ""),
        "fid": doc.get("farmerId", ""),
        "mid": doc.get("manufacturerId", ""),
        "hqt": hqt
    }

    if secret:
        msg = f"{payload['cid']}|{payload['hdt']}|{payload['fid']}|{payload['mid']}|{payload['hqt']}|{payload['ctp']}"
        sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
        payload["sig"] = base64.urlsafe_b64encode(sig[:12]).decode()

    return json.dumps(payload, separators=(",", ":"))

def _latest_harvest_doc(user_id: str, crop_id: str) -> Optional[dict]:
    return FarmerReq.find_one({"farmerId": user_id, "cropId": crop_id}, sort=[("_id", -1)])

@router.get("/rfid/payload_from_harvest")
def rfid_payload_from_harvest(cropId: str = Query(..., min_length=5), identity: Dict[str, Any] = Depends(auth_identity)):
    user_id = _require_farmer(identity)
    doc = _latest_harvest_doc(user_id, cropId)
    if not doc:
        raise HTTPException(status_code=404, detail=f"no_harvest_for_{cropId}")

    secret = os.environ.get("RFID_TAG_SECRET")
    tag_str = _compact_harvest_doc_to_tag(doc, secret)
    try:
        RfidPlans.insert_one({
            "farmerId": user_id,
            "cropId": cropId,
            "payload": json.loads(tag_str),
            "created_at": time.time()
        })
    except Exception:
        pass

    return {"ok": True, "payload": tag_str}

@router.post("/rfid/write_from_harvest")
def rfid_write_from_harvest(
    cropId: str = Query(..., min_length=5),
    esp32: Optional[str] = Query(None, description="http://<ip-or-host>"),
    identity: Dict[str, Any] = Depends(auth_identity)
):
    """
    Bridge to an ESP32 tag-writer endpoint. Best-effort; returns JSON.
    """
    user_id = _require_farmer(identity)
    doc = _latest_harvest_doc(user_id, cropId)
    if not doc:
        raise HTTPException(status_code=404, detail=f"no_harvest_for_{cropId}")

    secret = os.environ.get("RFID_TAG_SECRET")
    tag_str = _compact_harvest_doc_to_tag(doc, secret)

    base = (esp32 or os.environ.get("ESP32_BASE", "")).strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=500, detail="ESP32_BASE_not_configured")

    # optional ping
    try:
        requests.get(f"{base}/rfid/ping", timeout=3)
    except Exception:
        pass

    CONNECT_T = 2
    READ_T    = 25
    endpoints = ["/rfid/write", "/write", "/rfid/program", "/api/rfid/write"]

    def _try_once(url):
        try:
            return requests.post(url, json={"payload": tag_str}, timeout=(CONNECT_T, READ_T))
        except Exception as e:
            return e

    last = None
    for ep in endpoints:
        url = f"{base}{ep}"
        res = _try_once(url)
        if isinstance(res, Exception):
            last = res
            continue

        try:
            ctype = (res.headers.get("content-type") or "")
            body = res.json() if "application/json" in ctype else {}
        except Exception:
            body = {}

        if res.status_code == 200 and body.get("ok") is True:
            try:
                RfidEvents.insert_one({
                    "farmerId": user_id,
                    "cropId": cropId,
                    "payload": json.loads(tag_str),
                    "endpoint": ep,
                    "at": time.time()
                })
            except Exception:
                pass
            return {"ok": True, "endpoint": ep}

        if res.status_code == 409:
            raise HTTPException(status_code=409, detail="no_tag_present")

        if res.status_code == 404:
            last = res
            continue

        err_body = body if body else {"text": res.text[:200]}
        raise HTTPException(status_code=502, detail={"err": "esp32_write_status", "code": res.status_code, "resp": err_body})

    if isinstance(last, Exception):
        raise HTTPException(status_code=502, detail=f"esp32_write_fail:{last}")
    raise HTTPException(status_code=502, detail="esp32_no_known_write_endpoint")
