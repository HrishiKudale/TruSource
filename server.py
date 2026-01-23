# --- imports (dedupe) ---
import os, time, jwt, bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
from pymongo import MongoClient

# --- config ---
MONGO_URI        = os.environ.get("MONGO_URI", "mongodb://localhost:27017/crop_traceability_db")
JWT_SECRET_KEY   = os.environ.get("JWT_SECRET_KEY", "change-me-super-secret")
ACCESS_EXPIRES_H = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_H", "6"))
REFRESH_EXPIRES_D= int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_D", "14"))

app = FastAPI(title="Traceability Mobile API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mongo = MongoClient(MONGO_URI)
db = mongo.get_database()
users = db["users"]

# --- pydantic models (unchanged except EmailStr removed) ---
class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: str
    password: str = Field(..., min_length=6)
    role: Literal["farmer","manufacturer","distributor","retailer","transporter","warehousing"]
    phone: Optional[str] = None
    location: Optional[str] = None
    address: Optional[str] = None
    officeAddress: Optional[str] = None
    officeName: Optional[str] = None
    gstNumber: Optional[str] = None
    warehouseType: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _loose_email(cls, v: str) -> str:
        v = (v or "").strip()
        if "@" not in v or " " in v:
            raise ValueError("invalid email format (expected something like user@host)")
        return v

class LoginRequest(BaseModel):
    email: str
    password: str
    role: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _loose_email(cls, v: str) -> str:
        v = (v or "").strip()
        if "@" not in v or " " in v:
            raise ValueError("invalid email format (expected something like user@host)")
        return v

class RefreshRequest(BaseModel):
    refresh_token: str

# --- helpers ---
def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)

def _user_public_payload(u: dict) -> dict:
    return {"userId": u.get("userId"), "name": u.get("name",""), "email": u.get("email",""), "role": u.get("role","")}

# --- issue tokens with string sub and full user in 'user' ---
def _jwt_issue(identity: Dict[str, Any]) -> Dict[str, str]:
    now = _now_utc()
    access_exp  = now + timedelta(hours=ACCESS_EXPIRES_H)
    refresh_exp = now + timedelta(days=REFRESH_EXPIRES_D)

    # 'sub' MUST be a string. Keep full identity in 'user'.
    sub_val = str(identity.get("userId", ""))

    access = jwt.encode(
        {"sub": sub_val, "user": identity, "type": "access",
         "iat": int(now.timestamp()), "exp": int(access_exp.timestamp())},
        JWT_SECRET_KEY, algorithm="HS256"
    )
    refresh = jwt.encode(
        {"sub": sub_val, "user": identity, "type": "refresh",
         "iat": int(now.timestamp()), "exp": int(refresh_exp.timestamp())},
        JWT_SECRET_KEY, algorithm="HS256"
    )
    return {"access_token": access, "refresh_token": refresh}

# --- one HTTPBearer scheme for this router (docs will show a lock) ---
bearer = HTTPBearer(scheme_name="AccessToken", bearerFormat="JWT", auto_error=False)

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

# keep your existing imports, but REMOVE the "_jwt_decode" import from distributor_api
# from backend.fastapi.distributor_api import _jwt_decode, router as distributor_router


def _jwt_decode(token: str) -> Dict[str, Any]:
    try:
        # allow legacy tokens even if sub was a dict; modern ones have string sub + full identity in "user"
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"], options={"verify_sub": False})
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# --- auth routes (unchanged) ---
@app.post("/api/v1/auth/register")
def api_register(req: RegisterRequest):
    email = req.email.strip().lower()
    role  = req.role.strip().lower()
    if users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="User already exists")
    user_id = f"{role[:3].upper()}{os.urandom(3).hex().upper()}{int(time.time())}"
    hashed = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user_doc = {
        "userId": user_id, "name": req.name.strip(), "email": email, "password": hashed, "role": role,
        "phone": req.phone, "location": req.location,
        "address": req.address if role=="farmer" else None,
        "officeAddress": req.officeAddress if role!="farmer" else None,
        "officeName": req.officeName if role!="farmer" else None,
        "gstNumber": req.gstNumber if role!="farmer" else None,
        "warehouseType": req.warehouseType if role=="warehousing" else None,
        "createdAt": _now_utc(),
    }
    users.insert_one(user_doc)
    tokens = _jwt_issue(_user_public_payload(user_doc))
    return JSONResponse(status_code=201, content={"ok": True, "user": _user_public_payload(user_doc), **tokens})

@app.post("/api/v1/auth/login")
def api_login(req: LoginRequest):
    q: Dict[str, Any] = {"email": req.email.strip().lower()}
    if req.role: q["role"] = req.role.strip().lower()
    u = users.find_one(q)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if not bcrypt.checkpw(req.password.encode("utf-8"), u.get("password","").encode("utf-8")):
        raise HTTPException(status_code=400, detail="Invalid password")
    tokens = _jwt_issue(_user_public_payload(u))
    return {"ok": True, "user": _user_public_payload(u), **tokens}

@app.post("/api/v1/auth/refresh")
def api_refresh(req: RefreshRequest):
    try:
        payload = jwt.decode(req.refresh_token, JWT_SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    ident = payload.get("sub") or {}
    new = _jwt_issue(ident)
    return {"ok": True, "access_token": new["access_token"]}

@app.get("/api/v1/me")
def api_me(identity=Depends(auth_identity)):
    user_id = identity.get("userId")
    u = users.find_one({"userId": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user": _user_public_payload(u)}


# --- include routers ---
from backend.fastapi.farmer_api import router as farmer_router
from backend.fastapi.manufacturer_api import router as manufacturer_router
from backend.fastapi.distributor_api import router as distributor_router
from backend.fastapi.transporter_api import router as transporter_router
from backend.fastapi.retailer_api import router as retailer_router
from backend.fastapi.traceability_api import router as traceability_router 

app.include_router(farmer_router)
app.include_router(manufacturer_router)
app.include_router(distributor_router)
app.include_router(transporter_router)
app.include_router(retailer_router)
app.include_router(traceability_router)  

# --- diagnostics ---
@app.get("/_health")
def _health():
    return {"ok": True, "service": "fastapi-mobile", "ts": int(datetime.utcnow().timestamp())}



@app.get("/_whoami")
def _whoami(identity=Depends(auth_identity)):
    return {"ok": True, "identity": identity}
from typing import Optional

@app.get("/_debug/token")
def debug_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer)
):
    # Prefer parsed credentials (Swagger passes these when you click "Authorize")
    via_security = None
    if credentials and (credentials.scheme or "").lower() == "bearer":
        via_security = f"Bearer {credentials.credentials}"

    # Also show the raw headers for comparison (useful for curl/Postman)
    via_header = request.headers.get("authorization")
    via_custom = request.headers.get("access_token")
    return {
        "via_security_dependency": via_security,
        "authorization_header": via_header,
        "access_token_header": via_custom
    }

@app.get("/_debug/decode")
def debug_decode(
    request: Request,
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer)
):
    raw = None

    # 1) token from Security(HTTPBearer)
    if credentials and (credentials.scheme or "").lower() == "bearer":
        raw = credentials.credentials

    # 2) fallback: Authorization header
    if not raw:
        hdr = request.headers.get("authorization") or ""
        if hdr.lower().startswith("bearer "):
            raw = hdr.split(" ", 1)[1].strip()


    # 3) fallback: custom header (if you try odd setups)
    if not raw:
        hdr2 = request.headers.get("access_token") or ""
        if hdr2.lower().startswith("bearer "):
            raw = hdr2.split(" ", 1)[1].strip()
        elif hdr2:
            raw = hdr2

    # 4) fallback: query param ?token=
    if not raw and token:
        raw = token

    if not raw:
        return {"ok": False, "why": "no token found via Security, Authorization, access_token, or ?token="}

    try:
        payload = jwt.decode(raw, JWT_SECRET_KEY, algorithms=["HS256"], options={"verify_sub": False})
        return {"ok": True, "payload": payload}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    
    