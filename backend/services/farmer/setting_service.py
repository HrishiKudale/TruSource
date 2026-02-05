# backend/services/settings_service.py
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
from flask import current_app

from backend.mongo import mongo


ALLOWED_DOC_KEYS = {"aadhaar", "khasar"}
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}


class SettingsService:
    @staticmethod
    def get_user(user_id: str) -> Optional[Dict[str, Any]]:
        return mongo.db.users.find_one({"userId": user_id}, {"_id": 0})

    @staticmethod
    def update_profile(user_id: str, name: str, email: str, phone: str, profile_photo_url: Optional[str]) -> Dict[str, Any]:
        patch = {
            "name": (name or "").strip(),
            "email": (email or "").strip().lower(),
            "phone": (phone or "").strip(),
            "updated_at": datetime.now(timezone.utc),
        }
        if profile_photo_url:
            patch["profilePhotoUrl"] = profile_photo_url

        mongo.db.users.update_one({"userId": user_id}, {"$set": patch})
        return {"ok": True}

    @staticmethod
    def save_document(user_id: str, doc_key: str, file_storage) -> Dict[str, Any]:
        if doc_key not in ALLOWED_DOC_KEYS:
            return {"ok": False, "message": "Invalid docKey"}

        if not file_storage:
            return {"ok": False, "message": "file required"}

        filename = secure_filename(file_storage.filename or "")
        if not filename:
            return {"ok": False, "message": "bad filename"}

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXT:
            return {"ok": False, "message": "invalid file type"}

        # store to static/uploads/<userId>/
        rel_dir = f"uploads/{user_id}"
        abs_dir = os.path.join(current_app.static_folder, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        ts = int(datetime.utcnow().timestamp())
        stored_name = f"{doc_key}_{ts}{ext}"
        abs_path = os.path.join(abs_dir, stored_name)

        file_storage.save(abs_path)

        file_url = f"/static/{rel_dir}/{stored_name}"

        mongo.db.users.update_one(
            {"userId": user_id},
            {"$set": {
                f"documents.{doc_key}": {
                    "filename": stored_name,
                    "url": file_url,
                    "uploadedAt": datetime.utcnow(),
                },
                "updated_at": datetime.now(timezone.utc),
            }},
        )

        return {"ok": True, "filename": stored_name, "url": file_url}

    @staticmethod
    def update_preferences(user_id: str, language: Optional[str], harvest_notifications: Optional[bool]) -> Dict[str, Any]:
        patch = {}
        if language is not None:
            patch["preferences.language"] = language
        if harvest_notifications is not None:
            patch["preferences.harvestNotifications"] = bool(harvest_notifications)

        if not patch:
            return {"ok": True}

        patch["updated_at"] = datetime.now(timezone.utc)

        mongo.db.users.update_one({"userId": user_id}, {"$set": patch})
        return {"ok": True}

    @staticmethod
    def change_password_local(user_id: str, current_password: str, new_password: str) -> Dict[str, Any]:
        """
        This assumes your main backend Mongo 'users' doc stores 'password' hash (bcrypt).
        If password is stored ONLY in auth_api, then instead call auth_api endpoint here.
        """
        bcrypt = Bcrypt(current_app)

        u = mongo.db.users.find_one({"userId": user_id})
        if not u:
            return {"ok": False, "message": "User not found"}

        hashed = u.get("password")
        if not hashed:
            return {"ok": False, "message": "Password not available in this service"}

        if not bcrypt.check_password_hash(hashed, current_password or ""):
            return {"ok": False, "message": "Current password is incorrect"}

        if len(new_password or "") < 6:
            return {"ok": False, "message": "New password must be at least 6 characters"}

        new_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")

        mongo.db.users.update_one(
            {"userId": user_id},
            {"$set": {
                "password": new_hash,
                "passwordUpdatedAt": datetime.utcnow().strftime("%d %b %Y"),
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        return {"ok": True}
