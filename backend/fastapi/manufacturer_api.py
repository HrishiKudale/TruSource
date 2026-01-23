# backend/fastapi/manufacturer_api.py
# FastAPI router exposing Manufacturer dashboard data for your mobile app.
# - Reads the SAME MongoDB collections your Flask pages use
# - Verifies JWTs issued by your Flask /auth endpoints (shared JWT_SECRET_KEY)
# - Provides JSON endpoints mirroring manufacturer_dashboard.py

from __future__ import annotations
import os, json, math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from pymongo import MongoClient
import jwt

# ---------- Mongo & JWT config (MUST match Flask app.py) ----------
MONGO_URI      = os.environ.get("MONGO_URI", "mongodb://localhost:27017/crop_traceability_db")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-super-secret")

mongo      = MongoClient(MONGO_URI)
db         = mongo.get_database()
Users      = db["users"]
FarmerReq  = db["farmer_request"]
MfReq      = db["manufacturer_request"]
TransReq   = db["transporter_requests"]
RatesCol   = db["processing_rates"]

router = APIRouter(prefix="/api/v1/manufacturer", tags=["manufacturer"])

# --- one HTTPBearer scheme for this router (docs will show a lock) ---
bearer = HTTPBearer(scheme_name="AccessToken", bearerFormat="JWT", auto_error=False)


# ---------- Auth helpers (validate Flask-issued JWT access tokens) ----------
def _jwt_decode(token: str) -> Dict[str, Any]:
    try:
        # Your Flask tokens default to HS256
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
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

    # prefer new tokens: identity in 'user'; fallback to legacy 'sub'
    identity = payload.get("user")
    if not identity and isinstance(payload.get("sub"), dict):
        identity = payload["sub"]
    if not identity and isinstance(payload.get("sub"), str):
        identity = {"userId": payload["sub"]}

    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return identity

def _require_manufacturer(identity: Dict[str, Any]) -> str:
    role = (identity.get("role") or "").lower()
    if role != "manufacturer":
        raise HTTPException(status_code=403, detail="Only manufacturers can access this endpoint")
    uid = identity.get("userId")
    if not uid:
        raise HTTPException(status_code=401, detail="Missing userId in token")
    return uid

# ---------- Utilities copied from Flask dashboard (safe for API use) ----------
def _parse_dt(val):
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        try:
            return datetime.utcfromtimestamp(int(val))
        except Exception:
            return None
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:len(fmt)], fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None

def _status_display(s):
    if not s: return ""
    s_low = s.lower()
    if s_low.startswith("approved"): return "Approved"
    if "pending" in s_low:          return "Pending"
    return s.title()

def _month_bounds(dt_utc):
    start = dt_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_start = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    prev_day = start - timedelta(days=1)
    prev_start = prev_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, next_start, prev_start

def _derive_batch_code(doc: Dict[str, Any]) -> str:
    crop_id = (doc.get("cropId") or "CROP").replace(" ", "")
    dt = _parse_dt(doc.get("processedDate")) or _parse_dt(doc.get("receivedDate")) or datetime.utcnow()
    ymd = dt.strftime("%Y%m%d")
    tx = str(doc.get("txHash") or "")[-6:].upper() or "XXXXXX"
    return f"BATCH-{crop_id}-{ymd}-{tx}"

# ---------- Response models ----------
class RateCreate(BaseModel):
    cropType: str
    location: str
    ratePerKg: float
    harvestingCost: float
    packagingCost: float
    qualityAdjustment: float
    transportationCost: float
    bonusOrDiscount: float

# ---------- Core builders ----------
def _processed_batches_for(uid: str) -> Tuple[List[Dict[str, Any]], int, float]:
    cur = MfReq.find({"manufacturerId": uid})
    processed_batches: List[Dict[str, Any]] = []

    now = datetime.utcnow()
    this_mo_start, next_mo_start, prev_mo_start = _month_bounds(now)
    this_month_count = 0
    prev_month_count = 0
    total_processed = 0

    for d in cur:
        processed_dt = _parse_dt(d.get("processedDate"))
        received_dt  = _parse_dt(d.get("receivedDate"))
        ref_dt       = processed_dt or received_dt

        if ref_dt:
            if this_mo_start <= ref_dt < next_mo_start:
                this_month_count += 1
            if prev_mo_start <= ref_dt < this_mo_start:
                prev_month_count += 1

        total_processed += 1
        processed_batches.append({
            "cropId": d.get("cropId", ""),
            "cropType": d.get("cropType", ""),
            "receivedDate": d.get("receivedDate", ""),
            "processedDate": d.get("processedDate", ""),
            "txHash": d.get("txHash", ""),
            "destination": d.get("destination", d.get("distributorId", "")),
            "batchCode": d.get("batchCode") or _derive_batch_code(d),
        })

    trend = round(((this_month_count - prev_month_count) / prev_month_count) * 100.0, 1) if prev_month_count > 0 else 0.0
    return processed_batches, total_processed, trend

def _pending_farmer_requests(uid: str) -> List[Dict[str, Any]]:
    cursor = (
        FarmerReq.find({"manufacturerId": uid, "status": {"$in": ["Pending", "pending", "Pending (offline)"]}})
                 .sort([("created_at", -1), ("_id", -1)])
    )
    out, seen = [], set()
    for req in cursor:
        crop_id_raw  = (req.get("cropId") or "").strip()
        crop_type    = (req.get("cropType") or "").strip()
        norm_key     = crop_id_raw.upper() if crop_id_raw else f"TYPE::{crop_type.lower()}"
        if (not norm_key) or (norm_key in seen):
            continue
        seen.add(norm_key)
        out.append({
            "cropId": crop_id_raw,
            "cropType": crop_type,
            "harvestDate": req.get("harvestDate", ""),
            "harvesterName": req.get("harvesterName", ""),
            "manufacturerId": req.get("manufacturerId", ""),
            "status": _status_display(req.get("status", "")),
            "requestId": str(req.get("_id")),
            "approvedDate": req.get("approvedDate"),
        })
    return out

def _transporter_requests(uid: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int, int]:
    pending_filter  = {"recipientId": uid, "status": {"$regex": "^pending$", "$options": "i"}}
    approved_filter = {"recipientId": uid, "status": {"$regex": "^approved", "$options": "i"}}

    pend_cur = TransReq.find(pending_filter)
    appr_cur = TransReq.find(approved_filter)

    pending, approved = [], []
    for q, target in [(pend_cur, pending), (appr_cur, approved)]:
        for r in q:
            target.append({
                "requesterId":   r.get("requesterId", ""),
                "requesterRole": r.get("requesterRole", ""),
                "transporter_id": r.get("transporter_id"),
                "recipientId":   r.get("recipientId", ""),
                "cropId":        r.get("cropId", ""),
                "cropType":      r.get("cropType", ""),
                "harvestQuantity": r.get("harvestQuantity", ""),
                "status":        _status_display(r.get("status", "")),
                "timestamp":     r.get("timestamp", ""),
                "approvedDate":  r.get("approvedDate"),
            })

    pending_kpi  = TransReq.count_documents(pending_filter)
    approved_kpi = TransReq.count_documents(approved_filter)

    now = datetime.utcnow()
    monday = now - timedelta(days=now.weekday())
    week_count = TransReq.count_documents({**approved_filter, "approvedDate": {"$gte": monday}})
    if week_count == 0:
        seven_days = now - timedelta(days=7)
        week_count_est = 0
        for req in TransReq.find(approved_filter):
            ts = _parse_dt(req.get("approvedDate") or req.get("timestamp"))
            if ts and ts >= seven_days:
                week_count_est += 1
        week_count = week_count_est

    return pending, approved, pending_kpi, approved_kpi, week_count

# ---------- RECALL feed (on-chain) ----------
# This copy does NOT depend on Flask current_app.
from web3 import Web3
from blockchain_setup import web3 as w3  # reuse your configured provider

def _load_recall_min_abi() -> List[Dict[str, Any]]:
    candidates = [
        os.path.join(os.getcwd(), "RecallGuardSimpleABI.json"),
        os.path.join(os.path.dirname(__file__), "..", "RecallGuardSimpleABI.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "RecallGuardSimpleABI.json"),
    ]
    for p in map(os.path.abspath, candidates):
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    raise RuntimeError("RecallGuardSimpleABI.json not found. Place it in project root.")

_RECALL_ABI = _load_recall_min_abi()
_RECALL_ADDR = os.environ.get("RECALL_REGISTRY_ADDRESS")  # already set in Flask app.config

def _recall_contract() -> Any:
    if not _RECALL_ADDR:
        raise RuntimeError("RECALL_REGISTRY_ADDRESS env var not set")
    return w3.eth.contract(address=w3.to_checksum_address(_RECALL_ADDR), abi=_RECALL_ABI)

def _scan_recall_events_for_user(
    user_id: str,
    span_blocks: int = 2_000_000,
    from_block: Optional[int] = None,
    to_block: Optional[int]   = None,
) -> List[Dict[str, Any]]:
    c = _recall_contract()
    latest = w3.eth.block_number
    fb = 0 if span_blocks == 0 else max(0, latest - int(span_blocks))
    tb = latest
    if from_block is not None: fb = max(0, int(from_block))
    if to_block   is not None: tb = int(to_block)

    def safe_get_logs(ev, *, from_block: int, to_block: int):
        try:
            return ev.get_logs(from_block=from_block, to_block=to_block)
        except Exception:
            return ev.get_logs(from_block=hex(from_block), to_block=hex(to_block))

    evP = c.events.ParticipantsFiled()
    evR = c.events.RecallFiled()
    logs_p = safe_get_logs(evP, from_block=fb, to_block=tb)
    logs_r = safe_get_logs(evR, from_block=fb, to_block=tb)

    if not logs_p and not logs_r and fb != 0:
        logs_p = safe_get_logs(evP, from_block=0, to_block=tb)
        logs_r = safe_get_logs(evR, from_block=0, to_block=tb)

    index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for e in logs_p:
        args = e["args"]
        k = (args.get("cropId") or "", args.get("batchCode") or "")
        if k[0] and k[1]:
            index.setdefault(k, {})["pSeen"] = True

    for e in logs_r:
        args = e["args"]
        k = (args.get("cropId") or "", args.get("batchCode") or "")
        if k[0] and k[1]:
            index.setdefault(k, {})["rMeta"] = {
                "severity": int(args.get("severity") or 0),
                "filedAt": int(args.get("filedAt") or 0),
                "expiresAt": int(args.get("expiresAt") or 0),
                "contaminationType": args.get("contaminationType") or "",
            }

    out: List[Dict[str, Any]] = []
    for (cropId, batchCode), meta in index.items():
        try:
            reqUser, cropType, linkedIds, linkedRoles = c.functions.getParticipants(cropId, batchCode).call()
            is_me = (user_id == (reqUser or "")) or (user_id in (linkedIds or []))
            if not is_me:
                continue

            sev, filedAt, expAt, status, reasonURI, contType, location = c.functions.getRecallMeta(cropId, batchCode).call()
            out.append({
                "cropId": cropId,
                "batchCode": batchCode,
                "severity": int(sev),
                "filedAt": int(filedAt),
                "expiresAt": int(expAt),
                "status": int(status),
                "reasonURI": reasonURI,
                "contaminationType": contType,
                "location": location,
                "cropType": cropType,
                "requesterUserId": reqUser,
                "linkedCount": len(linkedIds or []),
            })
        except Exception:
            rm = meta.get("rMeta", {})
            if rm:
                out.append({
                    "cropId": cropId,
                    "batchCode": batchCode,
                    "severity": int(rm.get("severity") or 0),
                    "filedAt": int(rm.get("filedAt") or 0),
                    "expiresAt": int(rm.get("expiresAt") or 0),
                    "status": -1,
                    "reasonURI": "",
                    "contaminationType": rm.get("contaminationType") or "",
                    "location": "",
                    "cropType": "",
                    "requesterUserId": "",
                    "linkedCount": 0,
                })

    out.sort(key=lambda x: x.get("filedAt", 0), reverse=True)
    return out

# ---------- Routes ----------

@router.get("/overview")
def overview(
    identity: Dict[str, Any] = Depends(auth_identity)
):
    """
    Aggregate for the Manufacturer dashboard:
    - processed_batches + totals + trend
    - pending farmer requests
    - transporter pending/approved + KPIs
    """
    uid = _require_manufacturer(identity)

    processed, total_processed, trend_pct = _processed_batches_for(uid)
    pend, appr, kpi_pend, kpi_appr, week_ok = _transporter_requests(uid)
    farmer_pending = _pending_farmer_requests(uid)

    return {
        "ok": True,
        "userId": uid,
        "processed_batches": processed,
        "processed_kpi_total": total_processed,
        "processed_trend_pct": trend_pct,
        "manufacturer_requests": farmer_pending,
        "transporter_pending": pend,
        "transporter_approved": appr,
        "pending_transport_kpi": kpi_pend,
        "approved_shipments_kpi": kpi_appr,
        "approved_shipments_this_week": week_ok,
    }

@router.get("/processed")
def processed(
    identity: Dict[str, Any] = Depends(auth_identity)
):
    uid = _require_manufacturer(identity)
    items, total, trend = _processed_batches_for(uid)
    return {"ok": True, "items": items, "total": total, "trend_pct": trend}

@router.get("/requests/pending")
def requests_pending(
    identity: Dict[str, Any] = Depends(auth_identity)
):
    uid = _require_manufacturer(identity)
    return {"ok": True, "items": _pending_farmer_requests(uid)}

@router.get("/transporter")
def transporter_all(
    identity: Dict[str, Any] = Depends(auth_identity)
):
    uid = _require_manufacturer(identity)
    pend, appr, kpi_pend, kpi_appr, week_ok = _transporter_requests(uid)
    return {
        "ok": True,
        "pending": pend,
        "approved": appr,
        "pending_kpi": kpi_pend,
        "approved_kpi": kpi_appr,
        "approved_this_week": week_ok,
    }

# ----- Processing rates (JSON) -----
@router.get("/rates")
def list_rates(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_manufacturer(identity)
    items: List[Dict[str, Any]] = []
    cur = (RatesCol.find({"manufacturerId": uid})
                    .sort([("created_at", -1), ("_id", -1)]))
    for d in cur:
        d["_id"] = str(d.get("_id"))
        items.append(d)
    return {"ok": True, "items": items}

@router.post("/rates")
def create_rate(
    body: RateCreate,
    identity: Dict[str, Any] = Depends(auth_identity)
):
    uid = _require_manufacturer(identity)
    doc = {
        "manufacturerId": uid,
        "cropType": body.cropType,
        "location": body.location,
        "ratePerKg": float(body.ratePerKg),
        "harvestingCost": float(body.harvestingCost),
        "packagingCost": float(body.packagingCost),
        "qualityAdjustment": float(body.qualityAdjustment),
        "transportationCost": float(body.transportationCost),
        "bonusOrDiscount": float(body.bonusOrDiscount),
        "created_at": datetime.utcnow(),
    }
    try:
        RatesCol.insert_one(doc)
    except Exception:
        raise HTTPException(status_code=500, detail="db_write_failed")
    return {"ok": True}

# ----- Recall notifications (on-chain) -----
@router.get("/recall/notifications")
def recall_notifications(
    span: int = Query(2_000_000, ge=0),
    fromBlock: Optional[int] = Query(None),
    toBlock: Optional[int]   = Query(None),
    identity: Dict[str, Any] = Depends(auth_identity)
):
    uid = _require_manufacturer(identity)
    try:
        items = _scan_recall_events_for_user(uid, span_blocks=span, from_block=fromBlock, to_block=toBlock)
        return {"ok": True, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
