# backend/routes/auth/auth_routes.py
#
# FINAL – Remote Auth API compatible
# - USE_REMOTE_AUTH_API=1 → Uses Render Auth API
# - USE_REMOTE_AUTH_API=0 → Uses local Mongo (dev only)

from __future__ import annotations

import os
import base64
from io import BytesIO

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

# Remote Auth API client
from backend.services.auth_api_client import (
    login as auth_api_login,
    register as auth_api_register,
    AuthApiError,
)

# Local Mongo (lazy import)
def _get_mongo():
    from backend.mongo import mongo
    return mongo

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
USE_REMOTE_AUTH_API = os.getenv("USE_REMOTE_AUTH_API", "0") == "1"

auth_bp = Blueprint("auth", __name__)

_bcrypt: Bcrypt | None = None


def get_bcrypt() -> Bcrypt:
    global _bcrypt
    if _bcrypt is None:
        _bcrypt = Bcrypt(current_app)
    return _bcrypt


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _public_user(u: dict) -> dict:
    return {
        "userId": u.get("userId"),
        "name": u.get("name", ""),
        "email": u.get("email", ""),
        "role": u.get("role", ""),
    }


def _issue_tokens(user: dict):
    ident = _public_user(user)
    return (
        create_access_token(identity=ident),
        create_refresh_token(identity=ident),
    )


def _norm(v: str | None) -> str:
    return (v or "").strip().lower()


# -------------------------------------------------------------------
# HTML: Login
# -------------------------------------------------------------------
@auth_bp.route("/newlogin", methods=["GET", "POST"])
def newlogin():
    bcrypt = get_bcrypt()

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        email = _norm(data.get("email"))
        password = data.get("password") or ""
        role = _norm(data.get("role"))

        if not email or not password or not role:
            return jsonify(success=False, message="Email, password, role required"), 400

        # ==========================
        # REMOTE AUTH MODE
        # ==========================
        if USE_REMOTE_AUTH_API:
            try:
                out = auth_api_login(email, password, role)
            except AuthApiError as e:
                return jsonify(success=False, message=str(e)), 401
            except Exception as e:
                return jsonify(success=False, message=f"Auth API error: {e}"), 500

            user = out.get("user", {})
            session["user_id"] = user.get("userId")
            session["role"] = user.get("role")
            session["username"] = user.get("name", "")

            return jsonify(
                success=True,
                role=user.get("role"),
                access_token=out.get("access_token"),
                refresh_token=out.get("refresh_token"),
            ), 200

        # ==========================
        # LOCAL MONGO MODE (DEV)
        # ==========================
        mongo = _get_mongo()
        user = mongo.db.users.find_one({"email": email, "role": role})
        if not user:
            return jsonify(success=False, message="User not found"), 404

        if not bcrypt.check_password_hash(user["password"], password):
            return jsonify(success=False, message="Invalid password"), 401

        session["user_id"] = user["userId"]
        session["role"] = user["role"]
        session["username"] = user.get("name", "")

        access, refresh = _issue_tokens(user)
        return jsonify(
            success=True,
            role=user["role"],
            access_token=access,
            refresh_token=refresh,
        ), 200

    return render_template("newlogin.html")


# -------------------------------------------------------------------
# HTML: Registration
# -------------------------------------------------------------------
@auth_bp.route("/newregister", methods=["GET", "POST"])
def newregister():
    if request.method == "POST":
        form = request.form.to_dict()
        form["email"] = _norm(form.get("email"))
        form["role"] = _norm(form.get("role"))

        if USE_REMOTE_AUTH_API:
            try:
                out = auth_api_register(form)
            except AuthApiError as e:
                return jsonify(message=str(e)), 400
            except Exception as e:
                return jsonify(message=f"Auth API error: {e}"), 500

            user = out.get("user", {})
            user_id = user.get("userId")

            # QR
            profile_url = url_for("auth.user_profile", user_id=user_id, _external=True)
            os.makedirs("static/qrcodes", exist_ok=True)
            qr_path = f"static/qrcodes/{user_id}.png"
            qrcode.make(profile_url).save(qr_path)

            session["user_id"] = user_id
            session["user_role"] = user.get("role")
            session["user_name"] = user.get("name")

            return redirect(url_for("auth.registration_success"))

        # LOCAL DEV ONLY
        return jsonify(message="Local registration disabled in production"), 400

    return render_template("newregister.html")


@auth_bp.route("/registration-success")
def registration_success():
    return render_template(
        "registration_success.html",
        user_name=session.get("user_name"),
        user_id=session.get("user_id"),
        role=session.get("user_role"),
    )


# -------------------------------------------------------------------
# JSON: /auth/login (API)
# -------------------------------------------------------------------
@auth_bp.post("/auth/login")
def api_login():
    data = request.get_json(silent=True) or {}
    email = _norm(data.get("email"))
    password = data.get("password") or ""
    role = _norm(data.get("role"))

    if USE_REMOTE_AUTH_API:
        try:
            out = auth_api_login(email, password, role)
            return jsonify(ok=True, **out), 200
        except AuthApiError as e:
            return jsonify(ok=False, message=str(e)), 401

    return jsonify(ok=False, message="Local login disabled"), 400


# -------------------------------------------------------------------
# JSON: /auth/register (API)
# -------------------------------------------------------------------
@auth_bp.post("/auth/register")
def api_register():
    if USE_REMOTE_AUTH_API:
        try:
            out = auth_api_register(request.get_json() or {})
            return jsonify(ok=True, **out), 201
        except AuthApiError as e:
            return jsonify(ok=False, message=str(e)), 400

    return jsonify(ok=False, message="Local register disabled"), 400


# -------------------------------------------------------------------
# JSON: /auth/refresh
# -------------------------------------------------------------------
@auth_bp.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    ident = get_jwt_identity()
    return jsonify(
        ok=True,
        access_token=create_access_token(identity=ident),
    ), 200


# -------------------------------------------------------------------
# HTML: User profile + QR
# -------------------------------------------------------------------
@auth_bp.route("/user/<user_id>")
def user_profile(user_id: str):
    # In remote mode, profile data should come from Auth API later
    profile_url = url_for("auth.user_profile", user_id=user_id, _external=True)

    qr = qrcode.make(profile_url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)

    qr_b64 = base64.b64encode(buf.read()).decode()
    return render_template(
        "user_card.html",
        user={"userId": user_id},
        qr_image=f"data:image/png;base64,{qr_b64}",
    )
