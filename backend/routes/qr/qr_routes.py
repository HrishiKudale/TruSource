# backend/routes/qr/qr_routes.py

from flask import Blueprint, jsonify, send_file, request
import os
import qrcode
from io import BytesIO
from backend.mongo import mongo


qr_bp = Blueprint("qr_bp", __name__, url_prefix="/qr")


# ---------------------------------------------------
# GENERATE QR IMAGE AND STORE METADATA
# ---------------------------------------------------
@qr_bp.post("/generate")
def generate_qr():
    """
    Create a QR code from a payload and return the saved file path.
    """
    data = request.json or {}
    payload = data.get("payload")

    if not payload:
        return jsonify({"ok": False, "err": "payload is required"}), 400

    # Generate QR
    img = qrcode.make(payload)

    os.makedirs("static/qrcodes", exist_ok=True)
    filename = f"qr_{mongo.db.qr_codes.count_documents({}) + 1}.png"
    filepath = os.path.join("static/qrcodes", filename)

    img.save(filepath)

    # Save metadata
    mongo.db.qr_codes.insert_one({
        "payload": payload,
        "file": filepath
    })

    return jsonify({"ok": True, "file": filepath})


# ---------------------------------------------------
# DOWNLOAD QR (served file)
# ---------------------------------------------------
@qr_bp.get("/download")
def download_qr():
    file_path = request.args.get("file")
    if not file_path or not os.path.isfile(file_path):
        return jsonify({"ok": False, "err": "Invalid file"}), 400

    return send_file(file_path, as_attachment=True)


# ---------------------------------------------------
# LIST ALL SAVED QR CODES
# ---------------------------------------------------
@qr_bp.get("/list")
def list_qr_codes():
    cur = mongo.db.qr_codes.find().sort([("_id", -1)])
    data = []
    for d in cur:
        d["_id"] = str(d["_id"])
        data.append(d)

    return jsonify({"ok": True, "items": data})
