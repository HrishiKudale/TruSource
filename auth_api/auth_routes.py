# auth_api/auth_routes.py
import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, create_refresh_token, JWTManager, get_jwt_identity, jwt_required
from pymongo import MongoClient

auth_bp = Blueprint("auth", __name__)
bcrypt = Bcrypt()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["crop_traceability_db"]
users = db["users"]

# If this file is in a Flask app, ensure JWTManager(app) is created in your app factory.
# (No change needed here if already done.)

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


def _claims_from_public_user(pu: dict) -> dict:
    # ✅ goes into JWT payload as extra claims, NOT as subject
    return {
        "role": pu.get("role", ""),
        "name": pu.get("name", ""),
        "email": pu.get("email", ""),
    }


def _norm(v):
    return (v or "").strip()


def _norm_email(v):
    return (v or "").strip().lower()


@auth_bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict(flat=True) or {}

    user_id = _norm(data.get("userId") or data.get("user_id"))
    name = _norm(data.get("name"))
    email = _norm_email(data.get("email"))
    password = data.get("password") or ""
    role = _norm(data.get("role")).lower()

    if not user_id:
        return jsonify(message="userId is required"), 400
    if not name:
        return jsonify(message="Name is required"), 400
    if not email:
        return jsonify(message="Email is required"), 400
    if not password:
        return jsonify(message="Password is required"), 400
    if not role:
        return jsonify(message="Role is required"), 400

    if users.find_one({"userId": user_id}):
        return jsonify(message="UserId already exists"), 409
    if users.find_one({"email": email, "role": role}):
        return jsonify(message="User already exists for this role"), 409

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    now = datetime.now(timezone.utc)

    doc = dict(data)
    doc.pop("_id", None)

    doc["userId"] = user_id
    doc["name"] = name
    doc["email"] = email
    doc["role"] = role
    doc["password"] = hashed
    doc["created_at"] = now
    doc["updated_at"] = now

    users.insert_one(doc)

    ident = _public_user(doc)
    claims = _claims_from_public_user(ident)

    # ✅ IMPORTANT: identity MUST be a string
    access = create_access_token(identity=ident["userId"], additional_claims=claims)
    refresh = create_refresh_token(identity=ident["userId"], additional_claims=claims)

    return jsonify(user=ident, access_token=access, refresh_token=refresh), 201


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
    claims = _claims_from_public_user(ident)

    # ✅ IMPORTANT: identity MUST be a string
    access = create_access_token(identity=ident["userId"], additional_claims=claims)
    refresh = create_refresh_token(identity=ident["userId"], additional_claims=claims)

    return jsonify(user=ident, access_token=access, refresh_token=refresh), 200


@auth_bp.get("/users/<user_id>")
def get_user(user_id: str):
    user = users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        return jsonify(message="User not found"), 404
    return jsonify(user=user), 200


# ✅ optional refresh in AUTH SERVICE (recommended)
@auth_bp.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()  # ✅ string userId
    # in refresh, claims will also be present; you can copy them or re-fetch user
    return jsonify(ok=True, access_token=create_access_token(identity=user_id)), 200
