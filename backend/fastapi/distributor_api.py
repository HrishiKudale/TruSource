# backend/fastapi/distributor_api.py
from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from pymongo import MongoClient
import jwt

# ------------ Mongo / JWT (must match Flask) ------------
MONGO_URI      = os.environ.get("MONGO_URI", "mongodb://localhost:27017/crop_traceability_db")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-super-secret")

mongo = MongoClient(MONGO_URI)
db    = mongo.get_database()
ManReq = db["manufacturer_request"]
TransReq = db["transporter_requests"]
QrCodes = db["qr_codes"]

router = APIRouter(prefix="/api/v1/distributor", tags=["distributor"])

# --- one HTTPBearer scheme for this router (docs will show a lock) ---
bearer = HTTPBearer(scheme_name="AccessToken", bearerFormat="JWT", auto_error=False)

# ------------ JWT helpers ------------
def _jwt_decode(token: str) -> Dict[str, Any]:
    try:
        # allow legacy tokens with dict sub
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

    # prefer new tokens: identity in 'user'; fallback to legacy 'sub'
    identity = payload.get("user")
    if not identity and isinstance(payload.get("sub"), dict):
        identity = payload["sub"]
    if not identity and isinstance(payload.get("sub"), str):
        identity = {"userId": payload["sub"]}

    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return identity

def _require_distributor(identity: Dict[str, Any]) -> str:
    role = (identity.get("role") or "").lower()
    if role != "distributor":
        raise HTTPException(status_code=403, detail="Only distributors can access this endpoint")
    uid = identity.get("userId")
    if not uid:
        raise HTTPException(status_code=401, detail="Missing userId in token")
    return uid

# ------------ Utils (mirror your Flask helpers) ------------
def _parse_dt(val):
    if isinstance(val, datetime): return val
    if isinstance(val, (int, float)):
        try: return datetime.utcfromtimestamp(int(val))
        except Exception: return None
    if not val: return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try: return datetime.strptime(s[:len(fmt)], fmt)
        except Exception: pass
    try: return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception: return None

def _status_display(s):
    if not s: return ""
    s_low = str(s).lower()
    if s_low.startswith("approved"): return "Approved"
    if "pending" in s_low:          return "Pending"
    return str(s).title()

def _month_bounds(dt_utc):
    start = dt_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_start = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    prev_day = start - timedelta(days=1)
    prev_start = prev_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, next_start, prev_start

# ------------ Builders (pure data) ------------
def _incoming_for_distributor(uid: str):
    now = datetime.utcnow()
    this_mo_start, next_mo_start, prev_mo_start = _month_bounds(now)

    # NOTE: Your Flask code queries "distributor_id"
    in_cursor = ManReq.find({"distributor_id": uid}).sort([("processedDate", -1), ("receivedDate", -1), ("_id", -1)])

    incoming: List[Dict[str, Any]] = []
    this_mo, prev_mo = 0, 0
    for d in in_cursor:
        rec_dt = _parse_dt(d.get("processedDate")) or _parse_dt(d.get("receivedDate"))
        if rec_dt:
            if this_mo_start <= rec_dt < next_mo_start: this_mo += 1
            if prev_mo_start <= rec_dt < this_mo_start: prev_mo += 1
        incoming.append({
            "requestId": str(d.get("_id")),
            "cropId": d.get("cropId", ""),
            "cropType": d.get("cropType", ""),
            "manufacturerId": d.get("manufacturerId", ""),
            "processedDate": d.get("processedDate", ""),
            "receivedDate": d.get("receivedDate", ""),
            "status": _status_display(d.get("status", "")) or "Pending",
        })

    pending_kpi = sum(1 for r in incoming if r["status"].lower().startswith("pending"))
    total_kpi   = len(incoming)
    trend_pct   = round(((this_mo - prev_mo) / prev_mo) * 100.0, 1) if prev_mo > 0 else 0.0
    return incoming, pending_kpi, total_kpi, trend_pct

def _transporter_blocks(uid: str):
    pending_filter  = {"recipientId": uid, "status": {"$regex": "^pending$", "$options": "i"}}
    approved_filter = {"recipientId": uid, "status": {"$regex": "^approved", "$options": "i"}}

    pend, appr = [], []
    for req in TransReq.find(pending_filter).sort([("_id", -1)]):
        pend.append({
            "requesterId": req.get("requesterId", ""),
            "requesterRole": req.get("requesterRole", ""),
            "transporter_id": req.get("transporter_id"),
            "recipientId": req.get("recipientId", ""),
            "cropId": req.get("cropId", ""),
            "cropType": req.get("cropType", ""),
            "harvestQuantity": req.get("harvestQuantity", ""),
            "status": _status_display(req.get("status", "")),
            "timestamp": req.get("timestamp", ""),
        })
    for req in TransReq.find(approved_filter).sort([("_id", -1)]):
        appr.append({
            "requesterId": req.get("requesterId", ""),
            "requesterRole": req.get("requesterRole", ""),
            "transporter_id": req.get("transporter_id"),
            "recipientId": req.get("recipientId", ""),
            "cropId": req.get("cropId", ""),
            "cropType": req.get("cropType", ""),
            "harvestQuantity": req.get("harvestQuantity", ""),
            "status": _status_display(req.get("status", "")),
            "timestamp": req.get("timestamp", ""),
            "approvedDate": req.get("approvedDate"),
        })

    pending_kpi  = TransReq.count_documents(pending_filter)
    approved_kpi = TransReq.count_documents(approved_filter)

    # approved this week
    now = datetime.utcnow()
    monday = now - timedelta(days=now.weekday())
    week_count = TransReq.count_documents({**approved_filter, "approvedDate": {"$gte": monday}})
    if week_count == 0:
        seven_days = now - timedelta(days=7)
        est = 0
        for r in TransReq.find(approved_filter):
            ts = _parse_dt(r.get("approvedDate") or r.get("timestamp"))
            if ts and ts >= seven_days:
                est += 1
        week_count = est
    return pend, appr, pending_kpi, approved_kpi, week_count

def _recent_qr(uid: str) -> List[Dict[str, Any]]:
    try:
        qr_entries = list(QrCodes.find({"userId": uid}))
    except Exception:
        qr_entries = []
    # last 6 only (like chips)
    recent = [{
        "cropId": q.get("cropId", ""),
        "cropType": q.get("cropType", ""),
        "distributedDate": q.get("distributedDate", ""),
        "receiverName": q.get("receiverName", "-"),
    } for q in qr_entries[-6:]]
    return recent

# ------------ Endpoints ------------
@router.get("/overview")
def overview(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_distributor(identity)

    incoming, pend_in_kpi, total_in_kpi, trend = _incoming_for_distributor(uid)
    pend, appr, trn_p_kpi, trn_a_kpi, week_ok = _transporter_blocks(uid)
    recent_qr = _recent_qr(uid)

    return {
        "ok": True,
        "userId": uid,
        "incoming_requests": incoming,
        "total_incoming_kpi": total_in_kpi,
        "pending_incoming_kpi": pend_in_kpi,
        "incoming_trend_pct": trend,
        "transporter_pending": pend,
        "transporter_approved": appr,
        "pending_transport_kpi": trn_p_kpi,
        "approved_shipments_kpi": trn_a_kpi,
        "approved_shipments_this_week": week_ok,
        "recent_qr": recent_qr,
    }

@router.get("/incoming")
def incoming(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_distributor(identity)
    incoming, pend_in_kpi, total_in_kpi, trend = _incoming_for_distributor(uid)
    return {
        "ok": True,
        "items": incoming,
        "total_kpi": total_in_kpi,
        "pending_kpi": pend_in_kpi,
        "trend_pct": trend,
    }

@router.get("/transporter")
def transporter(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_distributor(identity)
    pend, appr, trn_p_kpi, trn_a_kpi, week_ok = _transporter_blocks(uid)
    return {
        "ok": True,
        "pending": pend,
        "approved": appr,
        "pending_kpi": trn_p_kpi,
        "approved_kpi": trn_a_kpi,
        "approved_this_week": week_ok,
    }

@router.get("/qr/recent")
def recent_qr(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_distributor(identity)
    return {"ok": True, "items": _recent_qr(uid)}
