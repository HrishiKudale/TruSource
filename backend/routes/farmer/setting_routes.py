# backend/routes/settings_routes.py
from __future__ import annotations

from flask import Blueprint, render_template, session, request, jsonify

from backend.services.farmer.setting_service import SettingsService


settings_bp = Blueprint("settings_bp", __name__, url_prefix="/settings")


def _require_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return user_id


@settings_bp.get("")
def settings_page():
    user_id = _require_user()
    if not user_id:
        return render_template("newlogin.html"), 401

    user = SettingsService.get_user(user_id) or {}
    return render_template("Setting.html", user=user,active_page="setting")


@settings_bp.post("/profile")
def update_profile():
    user_id = _require_user()
    if not user_id:
        return jsonify(ok=False, message="auth"), 401

    name = request.form.get("name", "")
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")

    photo = request.files.get("profilePhoto")
    photo_url = None
    if photo:
        # reuse document saver logic but store under documents? no.
        # simple: store as documents.profilePhoto (or direct field)
        out = SettingsService.save_document(user_id, "aadhaar" if False else "aadhaar", None)  # placeholder (not used)

        # real: quick save file into /static/uploads/<userId>/
        # for clean separation, you can implement a SettingsService.save_profile_photo()
        # keeping it minimal here:
        from werkzeug.utils import secure_filename
        import os
        from datetime import datetime
        from flask import current_app

        fn = secure_filename(photo.filename or "")
        ext = os.path.splitext(fn)[1].lower()
        if ext not in [".png",".jpg",".jpeg",".webp"]:
            return jsonify(ok=False, message="Profile photo must be image"), 400

        rel_dir = f"uploads/{user_id}"
        abs_dir = os.path.join(current_app.static_folder, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        stored = f"profile_{int(datetime.utcnow().timestamp())}{ext}"
        abs_path = os.path.join(abs_dir, stored)
        photo.save(abs_path)
        photo_url = f"/static/{rel_dir}/{stored}"

    SettingsService.update_profile(user_id, name, email, phone, photo_url)
    return jsonify(ok=True), 200


@settings_bp.post("/password")
def update_password():
    user_id = _require_user()
    if not user_id:
        return jsonify(ok=False, message="auth"), 401

    data = request.get_json(silent=True) or {}
    current_pw = data.get("currentPassword") or ""
    new_pw = data.get("newPassword") or ""
    confirm = data.get("confirmPassword") or ""

    if not current_pw or not new_pw or not confirm:
        return jsonify(ok=False, message="All fields required"), 400
    if new_pw != confirm:
        return jsonify(ok=False, message="New password and confirm password must match"), 400

    out = SettingsService.change_password_local(user_id, current_pw, new_pw)
    if not out.get("ok"):
        return jsonify(ok=False, message=out.get("message", "failed")), 400

    return jsonify(ok=True), 200


@settings_bp.post("/documents")
def upload_documents():
    user_id = _require_user()
    if not user_id:
        return jsonify(ok=False, message="auth"), 401

    doc_key = (request.form.get("docKey") or "").strip().lower()
    f = request.files.get("file")
    out = SettingsService.save_document(user_id, doc_key, f)
    if not out.get("ok"):
        return jsonify(ok=False, message=out.get("message", "upload failed")), 400
    return jsonify(ok=True, filename=out.get("filename"), url=out.get("url")), 200


@settings_bp.post("/preferences")
def update_preferences():
    user_id = _require_user()
    if not user_id:
        return jsonify(ok=False, message="auth"), 401

    data = request.get_json(silent=True) or {}
    language = data.get("language")
    harvest_notifications = data.get("harvestNotifications")

    out = SettingsService.update_preferences(user_id, language, harvest_notifications)
    if not out.get("ok"):
        return jsonify(ok=False, message=out.get("message", "failed")), 400
    return jsonify(ok=True), 200
