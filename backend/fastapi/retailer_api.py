# backend/fastapi/retailer_api.py
from __future__ import annotations
import os, re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from pymongo import MongoClient
from bson.objectid import ObjectId
import jwt

# ---------- Config (must match Flask) ----------
MONGO_URI      = os.environ.get("MONGO_URI", "mongodb://localhost:27017/crop_traceability_db")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-super-secret")

mongo = MongoClient(MONGO_URI)
db = mongo.get_database()
RetailInv = db["retailer_inventory"]
TransReq  = db["transporter_requests"]

router = APIRouter(prefix="/api/v1/retailer", tags=["retailer"])
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

def _require_retailer(identity: Dict[str, Any]) -> str:
    role = (identity.get("role") or "").lower()
    if role != "retailer":
        raise HTTPException(status_code=403, detail="Only retailers can access this endpoint")
    uid = identity.get("userId")
    if not uid:
        raise HTTPException(status_code=401, detail="Missing userId in token")
    return uid

# ---------- Helpers (mirrors Flask retailer_dashboard) ----------
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
    return str(s).title()

def _month_bounds(dt_utc: datetime):
    start = dt_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_start = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    prev_day = start - timedelta(days=1)
    prev_start = prev_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, next_start, prev_start

def _derive_batch_code_like(doc):
    crop_id = (doc.get("cropId") or "CROP").replace(" ", "")
    dt = _parse_dt(doc.get("receivedDate")) or _parse_dt(doc.get("created_at")) or datetime.utcnow()
    ymd = dt.strftime("%Y%m%d")
    tail = str(doc.get("_id") or "")[-6:].upper() or "XXXXXX"
    return f"BATCH-{crop_id}-{ymd}-{tail}"

# ---------- Models for actions ----------
class ApproveBody(BaseModel):
    crop_id: str

class InventoryCreateBody(BaseModel):
    cropId: str
    cropType: str
    batchId: Optional[str] = None
    location: Optional[str] = None
    status: str = "Pending"
    receivedDate: Optional[str] = None
    soldDate: Optional[str] = None
    retailPrice: float = 0.0

# ---------- Builders ----------
def _inventory(uid: str):
    # case-insensitive exact match like Flask
    uid_regex = {"$regex": f"^{re.escape(uid)}$", "$options": "i"}
    inv_cur = RetailInv.find({"retailerId": uid_regex}).sort([("created_at", -1), ("_id", -1)])

    now = datetime.utcnow()
    monday = now - timedelta(days=now.weekday())

    items, total_inventory_kpi, sold_this_week = [], 0, 0
    for d in inv_cur:
        total_inventory_kpi += 1
        sold_dt = _parse_dt(d.get("soldDate"))
        if sold_dt and sold_dt >= monday:
            sold_this_week += 1
        items.append({
            "cropId": d.get("cropId", ""),
            "cropType": d.get("cropType", ""),
            "batchId": d.get("batchId") or _derive_batch_code_like(d),
            "location": d.get("location", ""),
            "receivedDate": d.get("receivedDate", ""),
            "soldDate": d.get("soldDate", ""),
            "retailPrice": d.get("retailPrice", ""),
            "status": _status_display(d.get("status", "")),
        })
    return items, total_inventory_kpi, sold_this_week

def _transporter_blocks(uid: str):
    uid_regex = {"$regex": f"^{re.escape(uid)}$", "$options": "i"}
    trn_pending_filter  = {"recipientId": uid_regex, "status": {"$regex": "^pending$", "$options": "i"}}
    trn_approved_filter = {"recipientId": uid_regex, "status": {"$regex": "^approved", "$options": "i"}}

    pending, approved = [], []
    for req in TransReq.find(trn_pending_filter):
        pending.append({
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
    for req in TransReq.find(trn_approved_filter):
        approved.append({
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

    pending_kpi  = TransReq.count_documents(trn_pending_filter)
    approved_kpi = TransReq.count_documents(trn_approved_filter)
    return pending, approved, pending_kpi, approved_kpi

# ---------- Endpoints ----------
@router.get("/overview")
def overview(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_retailer(identity)

    inv, total_inventory_kpi, sold_this_week = _inventory(uid)
    pend, appr, pend_tr_kpi, appr_tr_kpi = _transporter_blocks(uid)

    return {
        "ok": True,
        "userId": uid,
        "inventory_items": inv,
        "total_inventory_kpi": total_inventory_kpi,
        "sales_this_week": sold_this_week,
        "transporter_pending": pend,
        "transporter_approved": appr,
        "pending_transport_kpi": pend_tr_kpi,
        "approved_shipments_kpi": appr_tr_kpi,
    }

@router.get("/inventory")
def inventory(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_retailer(identity)
    inv, total_inventory_kpi, sold_this_week = _inventory(uid)
    return {
        "ok": True,
        "items": inv,
        "total_inventory_kpi": total_inventory_kpi,
        "sales_this_week": sold_this_week,
    }

@router.post("/inventory")
def inventory_create(body: InventoryCreateBody, identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_retailer(identity)
    doc = {
        "retailerId": uid,
        "cropId": body.cropId,
        "cropType": body.cropType,
        "batchId": body.batchId,
        "location": body.location,
        "status": body.status,
        "receivedDate": body.receivedDate,
        "soldDate": body.soldDate,
        "retailPrice": float(body.retailPrice),
        "created_at": datetime.utcnow(),
    }
    RetailInv.insert_one(doc)
    return {"ok": True}

@router.get("/transporter")
def transporter(identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_retailer(identity)
    pend, appr, pend_kpi, appr_kpi = _transporter_blocks(uid)
    return {
        "ok": True,
        "pending": pend,
        "approved": appr,
        "pending_kpi": pend_kpi,
        "approved_kpi": appr_kpi,
    }

@router.post("/transporter/approve")
def transporter_approve(body: ApproveBody, identity: Dict[str, Any] = Depends(auth_identity)):
    uid = _require_retailer(identity)
    uid_regex = {"$regex": f"^{re.escape(uid)}$", "$options": "i"}

    doc = TransReq.find_one({
        "recipientId": uid_regex,
        "cropId": body.crop_id,
        "status": {"$regex": "^pending$", "$options": "i"},
    })
    if not doc:
        raise HTTPException(status_code=404, detail="No matching pending request found")

    TransReq.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "Approved by Retailer", "approvedDate": datetime.utcnow()}}
    )
    return {"ok": True}
