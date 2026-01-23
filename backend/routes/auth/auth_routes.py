# backend/routes/auth/auth_routes.py

from __future__ import annotations

import os
import time
import base64
from io import BytesIO

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

import qrcode

from backend.mongo import mongo
from backend.blockchain import contract, web3, account, suggest_fees

# -------------------------------------------------------------------
# Blueprint
# -------------------------------------------------------------------
auth_bp = Blueprint("auth", __name__)

# We will use one shared Bcrypt instance per app via current_app
# but to keep compatibility with your existing pattern, we allow
# instantiating Bcrypt lazily.
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
    prefix = prefix_map.get(role.lower())
    if not prefix:
        return None
    # random + timestamp to keep IDs fairly unique
    return f"{prefix}{str(os.urandom(3).hex()).upper()}{int(time.time())}"


# -------------------------------------------------------------------
# HTML: Registration Page (GET/POST)
# -------------------------------------------------------------------
@auth_bp.route("/newregister", methods=["GET", "POST"])
def new_register():
    """
    Legacy HTML registration form.
    POST: form fields, writes user to Mongo, anchors selected roles on-chain,
          creates QR for user profile, sets session, redirects to success page.
    """
    bcrypt = get_bcrypt()

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        phone = request.form.get("phone")
        location = request.form.get("location")
        role = request.form.get("role")
        address = request.form.get("address")
        office_name = request.form.get("officeName")
        office_address = request.form.get("officeAddress")
        gst_number = request.form.get("gstNumber")
        warehouse_type = request.form.get("warehouseType")

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
            "role": role.lower(),
            "address": address if role.lower() == "farmer" else None,
            "officeAddress": office_address if role.lower() != "farmer" else None,
            "officeName": office_name if role.lower() != "farmer" else None,
            "gstNumber": gst_number if role.lower() != "farmer" else None,
            "warehouseType": warehouse_type if role.lower() == "warehousing" else None,
        }

        # Write to Mongo first
        mongo.db.users.insert_one(user_data)

        # Only anchor to chain for selected roles
        if role.lower() in ["farmer", "manufacturer", "distributor", "retailer"]:
            fn = contract.functions.registerUserId(user_id)
            try:
                gas_est = fn.estimate_gas({"from": account.address})
                prio, max_fee = suggest_fees()

                txn = fn.build_transaction(
                    {
                        "from": account.address,
                        "nonce": web3.eth.get_transaction_count(
                            account.address, "pending"
                        ),
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
                    return (
                        jsonify(
                            {"message": "Transaction failed on Polygon Amoy."}
                        ),
                        500,
                    )

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
        session["user_role"] = role.lower()

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

        email = form_data.get("email")
        password = form_data.get("password")
        role = form_data.get("role")

        if not email or not password:
            return (
                jsonify(
                    {"success": False, "message": "Email and password are required"}
                ),
                400,
            )

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
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Error fetching crops: {str(e)}",
                    }
                ),
                500,
            )

        # JWT tokens for mobile / SPA usage
        access, refresh = _issue_tokens(user)

        role_value = user["role"]
        return jsonify(
            {
                "success": True,
                "role": role_value,
                "access_token": access,
                "refresh_token": refresh,
            }
        )

    # GET => return HTML login page
    return render_template("newlogin.html")


# -------------------------------------------------------------------
# JSON: /auth/register (API)
# -------------------------------------------------------------------
@auth_bp.post("/auth/register")
def auth_register():
    """
    JSON registration endpoint.
    Body:
      { name, email, password, role, phone?, location?, address?, ... }
    Returns JWT access + refresh tokens.
    """
    bcrypt = get_bcrypt()
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "").strip().lower()

    if not (name and email and password and role):
        return (
            jsonify(
                ok=False,
                message="name, email, password, role are required",
            ),
            400,
        )

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

    # (Optional) You can also anchor to chain here if desired, similar to HTML register.

    access, refresh = _issue_tokens(user_doc)
    return (
        jsonify(
            ok=True,
            user=_user_public_payload(user_doc),
            access_token=access,
            refresh_token=refresh,
        ),
        201,
    )


# -------------------------------------------------------------------
# JSON: /auth/login (API)
# -------------------------------------------------------------------
@auth_bp.post("/auth/login")
def auth_login():
    """
    JSON login:
      { email, password, role? }
    Returns JWT tokens + user payload.
    Also sets Flask session for SSR dashboards.
    """
    bcrypt = get_bcrypt()
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "").strip().lower()  # optional filter

    if not (email and password):
        return jsonify(ok=False, message="Email and password are required"), 400

    query = {"email": email}
    if role:
        query["role"] = role

    user = mongo.db.users.find_one(query)
    if not user:
        return jsonify(ok=False, message="User not found"), 404
    if not bcrypt.check_password_hash(user["password"], password):
        return jsonify(ok=False, message="Invalid password"), 400

    # SSR session support
    session["user_id"] = user["userId"]
    session["role"] = user["role"]
    session["username"] = user.get("name", "")

    access, refresh = _issue_tokens(user)
    return (
        jsonify(
            ok=True,
            user=_user_public_payload(user),
            access_token=access,
            refresh_token=refresh,
        ),
        200,
    )


# -------------------------------------------------------------------
# JSON: /auth/refresh
# -------------------------------------------------------------------
@auth_bp.post("/auth/refresh")
@jwt_required(refresh=True)
def auth_refresh():
    """
    JWT refresh endpoint.
    Requires a valid refresh token; returns a new access token.
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
    """
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
