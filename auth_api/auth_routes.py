import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
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


def _norm(v):
    return (v or "").strip()


def _norm_email(v):
    return (v or "").strip().lower()


@auth_bp.post("/auth/register")
def register_user():
    data = request.get_json(silent=True)
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
    return jsonify(
        user=ident,
        access_token=create_access_token(identity=ident),
        refresh_token=create_refresh_token(identity=ident),
    ), 201


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
