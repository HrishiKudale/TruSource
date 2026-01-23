# backend/routes/farmer/record_harvest.py

from flask import Blueprint, request, jsonify, session
from datetime import datetime
from backend.mongo import mongo
from backend.services.farmer.harvest_service import HarvestService

harvest_bp = Blueprint("farmer_harvest", __name__, url_prefix="/farmer/harvest")


# ---------------------------------------------------
# RECORD HARVEST (POST)
# ---------------------------------------------------
@harvest_bp.post("/record")
def record_harvest():
    if session.get("role") != "farmer":
        return jsonify({"ok": False, "err": "unauthorized"}), 401

    farmer_id = session.get("user_id")

    try:
        payload = request.get_json()
        result = HarvestService.record_harvest(farmer_id, payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 400


# ---------------------------------------------------
# HARVEST QR LABELS
# ---------------------------------------------------
@harvest_bp.get("/qr")
def qr_labels():
    if session.get("role") != "farmer":
        return jsonify({"ok": False, "err": "unauthorized"}), 401

    farmer_id = session.get("user_id")

    return jsonify(HarvestService.get_qr_labels(farmer_id))


# ---------------------------------------------------
# DOWNLOAD QR FILE
# ---------------------------------------------------
@harvest_bp.get("/qr/download/<batch_id>")
def download_qr(batch_id):
    if session.get("role") != "farmer":
        return jsonify({"ok": False, "err": "unauthorized"}), 401

    return HarvestService.download_qr(batch_id)


# ---------------------------------------------------
# HARVEST BAG CRUD
# ---------------------------------------------------
@harvest_bp.get("/bags")
def harvest_bags():
    farmer_id = session.get("user_id")
    return jsonify(HarvestService.list_bags(farmer_id))


@harvest_bp.post("/bags/add")
def add_bag():
    farmer_id = session.get("user_id")
    payload = request.json
    return jsonify(HarvestService.add_bag(farmer_id, payload))


@harvest_bp.delete("/bags/delete/<bag_id>")
def delete_bag(bag_id):
    farmer_id = session.get("user_id")
    return jsonify(HarvestService.delete_bag(farmer_id, bag_id))
