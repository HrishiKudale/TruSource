# backend/routes/auth/auth_routes.py
#
# ✅ PythonAnywhere Free compatible (Option B)
# - Uses Remote Auth API over HTTPS when USE_REMOTE_AUTH_API=1
# - Falls back to local Mongo when USE_REMOTE_AUTH_API=0 (for local dev / paid hosting)
#
# ENV VARS (PythonAnywhere -> Web -> Environment variables)
#   USE_REMOTE_AUTH_API=1
#   AUTH_API_BASE_URL=https://YOUR-AUTH-API.onrender.com
#
# Note:
# - This file keeps your HTML routes (/newlogin, /newregister, /user/<id>)
# - It proxies /auth/login and /auth/register to the remote Auth API in remote mode
# - It removes hard dependency on backend.mongo when remote mode is enabled

from __future__ import annotations

import os
import time
import base64
from io import BytesIO

import requests
import qrcode

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    current_app,
)

from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)

# Blockchain imports remain (only used during registration anchoring)
from backend.blockchain import contract, web3, account, suggest_fees

# -------------------------------------------------------------------
# Remote Auth API toggles
# -------------------------------------------------------------------
USE_REMOTE_AUTH_API = os.getenv("USE_REMOTE_AUTH_API", "0") == "1"
AUTH_API_BASE_URL = os.getenv("AUTH_API_BASE_URL", "").rstrip("/")

def _auth_api_post(path: str, payload: dict, timeout: int = 20):
    """
    Posts JSON to Remote Auth API and returns (status_code, json_dict).
    Raises ValueError if response isn't JSON.
    """
    if not AUTH_API_BASE_URL:
        raise RuntimeError("AUTH_API_BASE_URL is not set")
    url = f"{AUTH_API_BASE_URL}{path}"
    r = requests.post(url, json=payload, timeout=timeout)
    return r.status_code, r.json()

def _auth_api_get(path: str, timeout: int = 20):
    if not AUTH_API_BASE_URL:
        raise RuntimeError("AUTH_API_BASE_URL is not set")
    url = f"{AUTH_API_BASE_URL}{path}"
    r = requests.get(url, timeout=timeout)
    return r.status_code, r.json()

# -------------------------------------------------------------------
# Local Mongo (import only when needed)
# -------------------------------------------------------------------
def _get_mongo():
    """
    Lazy import so PythonAnywhere free doesn't crash at import time.
    Only called when USE_REMOTE_AUTH_API is False.
    """
    from backend.mongo import mongo  # local PyMongo instance
    return mongo

# -------------------------------------------------------------------
# Blueprint
# -------------------------------------------------------------------
auth_bp = Blueprint("auth", __name__)

# We will use one shared Bcrypt instance per app via current_app
_bcrypt: Bcrypt | None = None

def get_bcrypt() -> Bcrypt:
    global _bcrypt
    if _bcrypt is None:
        _bcrypt = Bcrypt(current_app)
    return _bcrypt

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _user_public_payload(u: dict) -> dict:
    """Safe subset of user data to embed in JWT identity."""
    return {
        "userId": u.get("userId"),
        "name": u.get("name", ""),
        "email": u.get("email", ""),
        "role": u.get("role", ""),
    }

def _issue_tokens(user_doc: dict) -> tuple[str, str]:
    ident = _user_public_payload(user_doc)
    access = create_access_token(identity=ident)
    refresh = create_refresh_token(identity=ident)
    return access, refresh

def _raw_tx_bytes(signed):
    """Support different eth-account versions exposing raw tx bytes."""
    raw = getattr(signed, "rawTransaction", None)
    if raw is None:
        raw = getattr(signed, "raw_transaction", None)
    if raw is None:
        raise TypeError("SignedTransaction has no raw tx bytes")
    return raw

def generate_user_id(role: str) -> str | None:
    prefix_map = {
        "farmer": "FRM",
        "manufacturer": "MFG",
        "distributor": "DIST",
        "retailer": "RET",
        "transporter": "TRN",
        "warehousing": "WRH",
    }
    prefix = prefix_map.get((role or "").lower())
    if not prefix:
        return None
    return f"{prefix}{str(os.urandom(3).hex()).upper()}{int(time.time())}"

def _normalize_role(v: str | None) -> str:
    return (v or "").strip().lower()

def _clean_nullable(v):
    """Convert 'null', '', None -> None"""
    if v is None:
        return None
    if isinstance(v, str) and v.strip().lower() in ("", "null", "none"):
        return None
    return v

# -------------------------------------------------------------------
# HTML: Registration Page (GET/POST)
# -------------------------------------------------------------------
@auth_bp.route("/newregister", methods=["GET", "POST"])
def new_register():
    """
    Legacy HTML registration form.

    Remote mode (USE_REMOTE_AUTH_API=1):
      - Sends registration payload to Remote Auth API (/auth/register)
      - Optionally anchors on-chain here (kept from your current code)
      - Generates QR locally and stores metadata:
          - If you want QR metadata stored in Mongo, add endpoint in remote API later.
          - For now, QR image is generated + stored on PythonAnywhere filesystem.

    Local mode:
      - Writes user to Mongo locally (existing behavior)
      - Anchors selected roles on-chain
      - Creates QR + saves metadata to Mongo
    """
    bcrypt = get_bcrypt()

    if request.method == "POST":
        name = request.form.get("name")
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password")
        phone = request.form.get("phone")
        location = request.form.get("location")
        role = _normalize_role(request.form.get("role"))
        address = request.form.get("address")
        office_name = request.form.get("officeName")
        office_address = request.form.get("officeAddress")
        gst_number = request.form.get("gstNumber")
        warehouse_type = request.form.get("warehouseType")

        # -------------------------
        # REMOTE AUTH API MODE
        # -------------------------
        if USE_REMOTE_AUTH_API:
            try:
                status, api_data = _auth_api_post(
                    "/auth/register",
                    {
                        "name": name,
                        "email": email,
                        "password": password,
                        "phone": _clean_nullable(phone),
                        "location": _clean_nullable(location),
                        "role": role,
                        "address": _clean_nullable(address),
                        "officeName": _clean_nullable(office_name),
                        "officeAddress": _clean_nullable(office_address),
                        "gstNumber": _clean_nullable(gst_number),
                        "warehouseType": _clean_nullable(warehouse_type),
                    },
                )
            except Exception as e:
                return jsonify({"message": f"Auth API error: {str(e)}"}), 500

            if status not in (200, 201):
                # Try to match your previous error shape
                msg = api_data.get("message") or api_data.get("detail") or "Registration failed"
                return jsonify({"message": msg}), status

            user = api_data.get("user") or {}
            user_id = user.get("userId")
            if not user_id:
                return jsonify({"message": "Registration failed: missing userId"}), 500

            # (Optional) Anchor to chain here for selected roles
            if role in ["farmer", "manufacturer", "distributor", "retailer"]:
                fn = contract.functions.registerUserId(user_id)
                try:
                    gas_est = fn.estimate_gas({"from": account.address})
                    prio, max_fee = suggest_fees()

                    txn = fn.build_transaction(
                        {
                            "from": account.address,
                            "nonce": web3.eth.get_transaction_count(account.address, "pending"),
                            "chainId": 80002,  # Polygon Amoy
                            "gas": int(gas_est * 1.20),
                            "maxPriorityFeePerGas": prio,
                            "maxFeePerGas": max_fee,
                        }
                    )

                    signed = account.sign_transaction(txn)
                    tx_hash = web3.eth.send_raw_transaction(_raw_tx_bytes(signed))
                    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

                    if not receipt or receipt.status != 1:
                        # NOTE: To rollback remote DB insert, you need a DELETE endpoint in Auth API.
                        return jsonify({"message": "Transaction failed on Polygon Amoy."}), 500

                except Exception as e:
                    # NOTE: To rollback remote DB insert, you need a DELETE endpoint in Auth API.
                    return jsonify({"message": f"Blockchain error: {str(e)}"}), 500

            # ✅ Generate QR linking to user profile
            profile_url = url_for("auth.user_profile", user_id=user_id, _external=True)
            os.makedirs("static/qrcodes", exist_ok=True)
            qr = qrcode.make(profile_url)
            qr_filename = f"static/qrcodes/{user_id}.png"
            qr.save(qr_filename)

            # Session
            session["user_id"] = user_id
            session["qr_code_path"] = qr_filename
            session["user_name"] = name
            session["user_role"] = role

            return redirect(url_for("auth.registration_success"))

        # -------------------------
        # LOCAL MONGO MODE (existing behavior)
        # -------------------------
        mongo = _get_mongo()

        # Check duplicates
        existing_user = mongo.db.users.find_one({"email": email})
        if existing_user:
            return jsonify({"message": "User already exists"}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        user_id = generate_user_id(role)
        if not user_id:
            return "Invalid role provided.", 400

        user_data = {
            "userId": user_id,
            "name": name,
            "email": email,
            "password": hashed_password,
            "phone": phone,
            "location": location,
            "role": role,
            "address": address if role == "farmer" else None,
            "officeAddress": office_address if role != "farmer" else None,
            "officeName": office_name if role != "farmer" else None,
            "gstNumber": gst_number if role != "farmer" else None,
            "warehouseType": warehouse_type if role == "warehousing" else None,
        }

        # Write to Mongo first
        mongo.db.users.insert_one(user_data)

        # Only anchor to chain for selected roles
        if role in ["farmer", "manufacturer", "distributor", "retailer"]:
            fn = contract.functions.registerUserId(user_id)
            try:
                gas_est = fn.estimate_gas({"from": account.address})
                prio, max_fee = suggest_fees()

                txn = fn.build_transaction(
                    {
                        "from": account.address,
                        "nonce": web3.eth.get_transaction_count(account.address, "pending"),
                        "chainId": 80002,  # Polygon Amoy
                        "gas": int(gas_est * 1.20),
                        "maxPriorityFeePerGas": prio,
                        "maxFeePerGas": max_fee,
                    }
                )

                signed = account.sign_transaction(txn)
                tx_hash = web3.eth.send_raw_transaction(_raw_tx_bytes(signed))
                receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

                if not receipt or receipt.status != 1:
                    # rollback local insert if on-chain failed
                    mongo.db.users.delete_one({"userId": user_id})
                    return jsonify({"message": "Transaction failed on Polygon Amoy."}), 500

            except Exception as e:
                # rollback local insert if tx building/sending failed
                mongo.db.users.delete_one({"userId": user_id})
                return jsonify({"message": f"Blockchain error: {str(e)}"}), 500

        # ✅ Generate QR linking to user profile
        profile_url = url_for("auth.user_profile", user_id=user_id, _external=True)
        os.makedirs("static/qrcodes", exist_ok=True)
        qr = qrcode.make(profile_url)
        qr_filename = f"static/qrcodes/{user_id}.png"
        qr.save(qr_filename)

        # Save QR metadata
        mongo.db.qr_codes.insert_one(
            {"userId": user_id, "profileUrl": profile_url, "qrImagePath": qr_filename}
        )

        # Session
        session["user_id"] = user_id
        session["qr_code_path"] = qr_filename
        session["user_name"] = name
        session["user_role"] = role

        return redirect(url_for("auth.registration_success"))

    return render_template("newregister.html")

# -------------------------------------------------------------------
# HTML: Registration Success Page
# -------------------------------------------------------------------
@auth_bp.route("/registration-success", methods=["GET"])
def registration_success():
    user_name = session.get("user_name")
    user_id = session.get("user_id")
    role = session.get("user_role")

    return render_template(
        "registration_success.html", user_name=user_name, user_id=user_id, role=role
    )

# -------------------------------------------------------------------
# HTML + JSON: Login Page
# -------------------------------------------------------------------
@auth_bp.route("/newlogin", methods=["GET", "POST"])
def new_login():
    """
    GET -> render HTML login page.
    POST -> expects JSON {email, password, role}, returns JSON with tokens + role.
    Also sets server-side session for web dashboards.
    """
    bcrypt = get_bcrypt()

    if request.method == "POST":
        form_data = request.get_json() or {}

        email = (form_data.get("email") or "").strip().lower()
        password = form_data.get("password") or ""
        role = _normalize_role(form_data.get("role"))

        if not email or not password:
            return jsonify({"success": False, "message": "Email and password are required"}), 400

        # -------------------------
        # REMOTE AUTH API MODE
        # -------------------------
        if USE_REMOTE_AUTH_API:
            try:
                status, api_data = _auth_api_post(
                    "/auth/login",
                    {"email": email, "password": password, "role": role},
                )
            except Exception as e:
                return jsonify({"success": False, "message": f"Auth API error: {str(e)}"}), 500

            if status != 200:
                msg = api_data.get("message") or api_data.get("detail") or "Login failed"
                return jsonify({"success": False, "message": msg}), status

            user = api_data.get("user") or {}

            # Session for web SSR
            session["user_id"] = user.get("userId")
            session["role"] = user.get("role")
            session["username"] = user.get("name", "")

            # Optional: if your frontend expects these
            return jsonify(
                {
                    "success": True,
                    "role": user.get("role"),
                    "access_token": api_data.get("access_token"),
                    "refresh_token": api_data.get("refresh_token"),
                }
            ), 200

        # -------------------------
        # LOCAL MONGO MODE (existing behavior)
        # -------------------------
        mongo = _get_mongo()
        user = mongo.db.users.find_one({"email": email, "role": role})
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 400

        if not bcrypt.check_password_hash(user["password"], password):
            return jsonify({"success": False, "message": "Invalid password"}), 400

        # Session for web SSR
        session["user_id"] = user["userId"]
        session["role"] = user["role"]
        session["username"] = user.get("name", "")

        # Optional: fetch crops for farmer (kept from your code)
        from blockchain_setup import contract as crop_contract  # optional direct use

        try:
            crop_id = user.get("cropId")
            if crop_id:
                crop_data = crop_contract.functions.getCrop(crop_id).call()
                session["user_crops"] = crop_data or []
            else:
                session["user_crops"] = []
        except Exception as e:
            return jsonify({"success": False, "message": f"Error fetching crops: {str(e)}"}), 500

        # JWT tokens for mobile / SPA usage
        access, refresh = _issue_tokens(user)

        return jsonify(
            {
                "success": True,
                "role": user["role"],
                "access_token": access,
                "refresh_token": refresh,
            }
        ), 200

    # GET => return HTML login page
    return render_template("newlogin.html")

# -------------------------------------------------------------------
# JSON: /auth/register (API)
# -------------------------------------------------------------------
@auth_bp.post("/auth/register")
def auth_register():
    """
    JSON registration endpoint.
    In Remote mode: proxies to Remote Auth API.
    In Local mode: uses Mongo.
    """
    bcrypt = get_bcrypt()
    data = request.get_json(silent=True) or {}

    # -------------------------
    # REMOTE MODE
    # -------------------------
    if USE_REMOTE_AUTH_API:
        try:
            status, api_data = _auth_api_post("/auth/register", data)
        except Exception as e:
            return jsonify(ok=False, message=f"Auth API error: {str(e)}"), 500

        msg_ok = api_data.get("ok", True)
        if status not in (200, 201) or not msg_ok:
            msg = api_data.get("message") or api_data.get("detail") or "Registration failed"
            return jsonify(ok=False, message=msg), status

        # Optionally set session for SSR apps too
        user = api_data.get("user") or {}
        session["user_id"] = user.get("userId")
        session["role"] = user.get("role")
        session["username"] = user.get("name", "")

        return jsonify(
            ok=True,
            user=user,
            access_token=api_data.get("access_token"),
            refresh_token=api_data.get("refresh_token"),
        ), 201

    # -------------------------
    # LOCAL MODE (existing behavior)
    # -------------------------
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = _normalize_role(data.get("role"))

    if not (name and email and password and role):
        return jsonify(ok=False, message="name, email, password, role are required"), 400

    mongo = _get_mongo()
    if mongo.db.users.find_one({"email": email}):
        return jsonify(ok=False, message="User already exists"), 400

    user_id = generate_user_id(role)
    if not user_id:
        return jsonify(ok=False, message="Invalid role"), 400

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    user_doc = {
        "userId": user_id,
        "name": name,
        "email": email,
        "password": hashed,
        "role": role,
        "phone": data.get("phone"),
        "location": data.get("location"),
        "address": data.get("address") if role == "farmer" else None,
        "officeAddress": data.get("officeAddress") if role != "farmer" else None,
        "officeName": data.get("officeName") if role != "farmer" else None,
        "gstNumber": data.get("gstNumber") if role != "farmer" else None,
        "warehouseType": data.get("warehouseType") if role == "warehousing" else None,
    }

    mongo.db.users.insert_one(user_doc)

    access, refresh = _issue_tokens(user_doc)
    return jsonify(ok=True, user=_user_public_payload(user_doc), access_token=access, refresh_token=refresh), 201

# -------------------------------------------------------------------
# JSON: /auth/login (API)
# -------------------------------------------------------------------
@auth_bp.post("/auth/login")
def auth_login():
    """
    JSON login:
      { email, password, role? }
    In Remote mode: proxies to Remote Auth API.
    In Local mode: uses Mongo.
    """
    bcrypt = get_bcrypt()
    data = request.get_json(silent=True) or {}

    # -------------------------
    # REMOTE MODE
    # -------------------------
    if USE_REMOTE_AUTH_API:
        try:
            status, api_data = _auth_api_post("/auth/login", data)
        except Exception as e:
            return jsonify(ok=False, message=f"Auth API error: {str(e)}"), 500

        if status != 200 or not api_data.get("ok", True):
            msg = api_data.get("message") or api_data.get("detail") or "Login failed"
            return jsonify(ok=False, message=msg), status

        user = api_data.get("user") or {}
        session["user_id"] = user.get("userId")
        session["role"] = user.get("role")
        session["username"] = user.get("name", "")

        return jsonify(
            ok=True,
            user=user,
            access_token=api_data.get("access_token"),
            refresh_token=api_data.get("refresh_token"),
        ), 200

    # -------------------------
    # LOCAL MODE (existing behavior)
    # -------------------------
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = _normalize_role(data.get("role"))

    if not (email and password):
        return jsonify(ok=False, message="Email and password are required"), 400

    query = {"email": email}
    if role:
        query["role"] = role

    mongo = _get_mongo()
    user = mongo.db.users.find_one(query)
    if not user:
        return jsonify(ok=False, message="User not found"), 404

    if not bcrypt.check_password_hash(user["password"], password):
        return jsonify(ok=False, message="Invalid password"), 401

    session["user_id"] = user["userId"]
    session["role"] = user["role"]
    session["username"] = user.get("name", "")

    access, refresh = _issue_tokens(user)
    return jsonify(ok=True, user=_user_public_payload(user), access_token=access, refresh_token=refresh), 200

# -------------------------------------------------------------------
# JSON: /auth/refresh
# -------------------------------------------------------------------
@auth_bp.post("/auth/refresh")
@jwt_required(refresh=True)
def auth_refresh():
    """
    JWT refresh endpoint.
    Note: In Remote mode, refresh should be done against Remote API directly by client.
    This route remains for local mode usage.
    """
    ident = get_jwt_identity()
    new_access = create_access_token(identity=ident)
    return jsonify(ok=True, access_token=new_access), 200

# -------------------------------------------------------------------
# HTML: User Profile + QR (Card View)
# -------------------------------------------------------------------
@auth_bp.route("/user/<user_id>", methods=["GET"])
def user_profile(user_id: str):
    """
    Render a user card with an embedded QR code pointing back to this profile.
    Remote mode: expects Remote Auth API to provide a GET /users/<userId> endpoint.
                If you don't have it yet, this will show "User not found".
    Local mode: reads from Mongo.
    """
    user = None

    if USE_REMOTE_AUTH_API:
        # If you haven't implemented this in the remote API, add it there later.
        try:
            status, api_data = _auth_api_get(f"/users/{user_id}")
            if status == 200 and api_data.get("ok", True):
                user = api_data.get("user") or api_data  # support either shape
        except Exception:
            user = None
    else:
        mongo = _get_mongo()
        user = mongo.db.users.find_one({"userId": user_id})

    if not user:
        return "User not found", 404

    profile_url = url_for("auth.user_profile", user_id=user_id, _external=True)

    qr_img = qrcode.make(profile_url)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)

    qr_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    qr_data_uri = f"data:image/png;base64,{qr_base64}"

    return render_template("user_card.html", user=user, qr_image=qr_data_uri)
