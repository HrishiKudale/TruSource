# backend/fastapi/transporter_api.py
from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from pymongo import MongoClient
from bson.objectid import ObjectId
import jwt

MONGO_URI      = os.environ.get("MONGO_URI", "mongodb://localhost:27017/crop_traceability_db")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-super-secret")

mongo = MongoClient(MONGO_URI)
db    = mongo.get_database()
TransReq = db["transporter_requests"]

router = APIRouter(prefix="/api/v1/transporter", tags=["transporter"])
# --- one HTTPBearer scheme for this router (docs will show a lock) ---
bearer = HTTPBearer(scheme_name="AccessToken", bearerFormat="JWT", auto_error=False)
# ---------- JWT helpers ----------
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

def _require_transporter(identity: Dict[str, Any]) -> str:
    role = (identity.get("role") or "").lower()
    if role != "transporter":
        raise HTTPException(status_code=403, detail="Only transporters can access this endpoint")
    uid = identity.get("userId")
    if not uid:
        raise HTTPException(status_code=401, detail="Missing userId in token")
    return uid

# ---------- Helpers ----------
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
    if "pending" in s_low:           return "Pending"
    if s_low.startswith("estimate"):  return "Estimate Sent"
    if s_low.startswith("accept"):    return "Accepted"
    return str(s).title()

# ---------- Builders ----------
def _overview(uid: str):
    now = datetime.utcnow()
    monday = now - timedelta(days=now.weekday())

    pend_filter = {"transporter_id": uid, "status": {"$regex": "^pending$", "$options": "i"}}
    appr_filter = {"transporter_id": uid, "status": {"$regex": "^approved", "$options": "i"}}

    # pending table
    pending = []
    for req in TransReq.find(pend_filter).sort([("timestamp", -1), ("_id", -1)]):
        pending.append({
            "_id": str(req.get("_id")),
            "requesterId": req.get("requesterId", ""),
            "requesterRole": req.get("requesterRole", ""),
            "recipientId": req.get("recipientId", ""),
            "cropId": req.get("cropId", ""),
            "cropType": req.get("cropType", ""),
            "harvestQuantity": req.get("harvestQuantity", ""),
            "status": _status_display(req.get("status", "")),
            "timestamp": req.get("timestamp", ""),
        })

    # approved table (+ week KPI)
    approved, week_count = [], 0
    for req in TransReq.find(appr_filter).sort([("approvedDate", -1), ("_id", -1)]):
        ts = _parse_dt(req.get("approvedDate") or req.get("timestamp"))
        if ts and ts >= monday:
            week_count += 1
        approved.append({
            "requesterId": req.get("requesterId", ""),
            "requesterRole": req.get("requesterRole", ""),
            "recipientId": req.get("recipientId", ""),
            "transporter_id": req.get("transporter_id", ""),
            "cropId": req.get("cropId", ""),
            "cropType": req.get("cropType", ""),
            "harvestQuantity": req.get("harvestQuantity", ""),
            "status": _status_display(req.get("status", "")),
            "timestamp": req.get("timestamp", ""),
            "approvedDate": req.get("approvedDate"),
        })

    pending_kpi  = TransReq.count_documents(pend_filter)
    approved_kpi = TransReq.count_documents(appr_filter)

    # chips: latest 20 among pending+approved
    chips = list(TransReq.find(
        {"transporter_id": uid, "status": {"$regex": "^(pending|approved)", "$options": "i"}}
    ).sort([("approvedDate", -1), ("timestamp", -1), ("_id", -1)]).limit(20))

    assignment_chips = [{
        "cropId": d.get("cropId", ""),
        "cropType": d.get("cropType", ""),
        "recipientId": d.get("recipientId", ""),
        "requesterId": d.get("requesterId", ""),
        "status": _status_display(d.get("status", "")),
        "timestamp": d.get("timestamp", ""),
        "approvedDate": d.get("approvedDate"),
    } for d in chips]

    return pending, approved, assignment_chips, pending_kpi, approved_kpi, week_count

# ---------- Models for actions ----------
class EstimateBody(BaseModel):
    request_id: str
    base_charge: float = 0
    distance_charge: float = 0
    variable_costs: float = 0
    packaging_charge: float = 0
    urgency_charge: float = 0
    total_charge: float

class ApproveBody(BaseModel):
    crop_id: str

# ---------- Endpoints ----------
@router.get("/overview")
def overview(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_transporter(identity)
    pend, appr, chips, kpi_pend, kpi_appr, week_ok = _overview(uid)
    return {
        "ok": True,
        "userId": uid,
        "transporter_requests": pend,
        "approved_requests": appr,
        "assignment_chips": chips,
        "pending_requests_kpi": kpi_pend,
        "approved_shipments_kpi": kpi_appr,
        "shipments_this_week": week_ok,
    }

@router.get("/pending")
def pending(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_transporter(identity)
    pend, *_ = _overview(uid)
    return {"ok": True, "items": pend}

@router.get("/approved")
def approved(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_transporter(identity)
    _, appr, *_ = _overview(uid)
    return {"ok": True, "items": appr}

@router.post("/estimate")
def send_estimate(body: EstimateBody, identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_transporter(identity)
    try:
        _id = ObjectId(body.request_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request_id")

    upd = {
        "base_charge": float(body.base_charge),
        "distance_charge": float(body.distance_charge),
        "variable_costs": float(body.variable_costs),
        "packaging_charge": float(body.packaging_charge),
        "urgency_charge": float(body.urgency_charge),
        "total_charge": float(body.total_charge),
        "status": "Estimate Sent",
        "estimated_on": datetime.utcnow(),
    }

    res = TransReq.update_one({"_id": _id, "transporter_id": uid}, {"$set": upd})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="No matching request for this transporter")
    return {"ok": True}

@router.post("/approve")
def approve(body: ApproveBody, identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_transporter(identity)
    # Find a PENDING request by cropId for this transporter (mirror Flask logic)
    doc = TransReq.find_one({
        "transporter_id": uid,
        "cropId": body.crop_id,
        "status": {"$regex": "^pending$", "$options": "i"}
    })
    if not doc:
        raise HTTPException(status_code=404, detail="No matching pending request found")
    TransReq.update_one({"_id": doc["_id"]}, {"$set": {"status": "Approved by Transporter", "approvedDate": datetime.utcnow()}})
    return {"ok": True}
