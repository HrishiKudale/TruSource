import os
from datetime import datetime, timezone
import time



from backend.services.auth_api_client import register as auth_api_register, AuthApiError

# ✅ NEW imports
from backend.blockchain import generate_user_id, should_anchor_user, anchor_user_id_onchain
from flask import Blueprint, redirect, render_template, request, jsonify, session, url_for
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, create_refresh_token
from pymongo import MongoClient

auth_bp = Blueprint("auth", __name__)
bcrypt = Bcrypt()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["crop_traceability_db"]
users = db["users"]


@auth_bp.get("/health")
def health():
    return jsonify(ok=True), 200


def _public_user(u: dict) -> dict:
    return {
        "userId": u.get("userId"),
        "name": u.get("name", ""),
        "email": u.get("email", ""),
        "role": u.get("role", ""),
    }



USE_REMOTE_AUTH_API = os.getenv("USE_REMOTE_AUTH_API", "0") == "1"
auth_bp = Blueprint("auth", __name__)

def _norm(v: str | None) -> str:
    return (v or "").strip()

def _norm_email(v: str | None) -> str:
    return (v or "").strip().lower()

@auth_bp.route("/newregister", methods=["GET", "POST"])
def newregister():
    if request.method == "POST":
        form = request.form.to_dict()

        # ✅ normalize
        form["email"] = _norm_email(form.get("email"))
        form["role"] = _norm(form.get("role")).lower()
        form["name"] = _norm(form.get("name"))
        form["password"] = form.get("password") or ""

        # ✅ must-have fields validation (main app side)
        if not form.get("name"):
            return jsonify(message="Name is required"), 400
        if not form.get("email"):
            return jsonify(message="Email is required"), 400
        if not form.get("password"):
            return jsonify(message="Password is required"), 400
        if not form.get("role"):
            return jsonify(message="Role is required"), 400

        # =========================================================
        # ✅ REMOTE AUTH MODE (Render Auth Service)
        # =========================================================
        if USE_REMOTE_AUTH_API:
            # 1) Generate userId here (main app)
            user_id = generate_user_id(form["role"])
            if not user_id:
                return jsonify(message="Invalid role provided."), 400

            form["userId"] = user_id  # ✅ REQUIRED by auth service

            # 2) Anchor to blockchain if needed (before storing user in Mongo)
            if should_anchor_user(form["role"]):
                chain_res = anchor_user_id_onchain(user_id)
                if not chain_res.get("ok"):
                    return jsonify(message=chain_res.get("error", "Blockchain error")), 500

                # optional: store tx_hash in mongo too
                form["chain_tx_hash"] = chain_res.get("tx_hash")

            # 3) Register in Auth API (stores in Mongo, hashes password)
            try:
                out = auth_api_register(form)
            except AuthApiError as e:
                return jsonify(message=str(e)), 400
            except Exception as e:
                return jsonify(message=f"Auth API error: {e}"), 500

            user = out.get("user", {})
            user_id = user.get("userId") or form["userId"]
            session["user_id"] = user_id
            session["user_role"] = user.get("role") or form.get("role")
            session["user_name"] = user.get("name") or form.get("name")

            return redirect(url_for("auth.registration_success"))

        # =========================================================
        # LOCAL DEV MODE (optional)
        # =========================================================
        return jsonify(message="Local registration disabled in production"), 400

    return render_template("newregister.html")



@auth_bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = _norm_email(data.get("email"))
    password = data.get("password") or ""
    role = _norm(data.get("role")).lower()

    if not email or not password:
        return jsonify(message="Email and password are required"), 400
    if not role:
        return jsonify(message="Role is required"), 400

    user = users.find_one({"email": email, "role": role})
    if not user:
        return jsonify(message="User not found"), 404

    if not bcrypt.check_password_hash(user["password"], password):
        return jsonify(message="Invalid password"), 401

    ident = _public_user(user)
    return jsonify(
        user=ident,
        access_token=create_access_token(identity=ident),
        refresh_token=create_refresh_token(identity=ident),
    ), 200


@auth_bp.get("/users/<user_id>")
def get_user(user_id: str):
    user = users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        return jsonify(message="User not found"), 404
    return jsonify(user=user), 200


@auth_bp.get("/mongo-ping")
def mongo_ping():
    client.admin.command("ping")
    return jsonify(ok=True), 200
