import os
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

@auth_bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "").strip().lower()

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
