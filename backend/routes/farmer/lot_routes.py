# backend/routes/farmer/lot_routes.py

from flask import Blueprint, request, session, jsonify
from backend.models.farmer.lot_models import CompositeLotCreateModel
from backend.services.farmer.lot_service import LotService

# This MUST be named lot_bp so register_blueprints.py can import it.
lot_bp = Blueprint("farmer_lot", __name__, url_prefix="/api/lots")


# ---------------------------------------------------------
# POST /api/lots/composite
# ---------------------------------------------------------
@lot_bp.route("/composite", methods=["POST"])
def create_composite_lot():
    if session.get("role") != "farmer":
        return jsonify({"ok": False, "err": "unauthorized"}), 401

    farmer_id = session["user_id"]

    try:
        payload = CompositeLotCreateModel(**request.json)
        result = LotService.create_composite_lot(payload, farmer_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 400


# ---------------------------------------------------------
# GET /api/lots/composite
# ---------------------------------------------------------
@lot_bp.route("/composite", methods=["GET"])
def list_composite_lots():
    if session.get("role") != "farmer":
        return jsonify({"ok": False, "err": "unauthorized"}), 401

    farmer_id = session["user_id"]
    limit = int(request.args.get("limit", 50))

    return jsonify(LotService.list_composite_lots(farmer_id, limit))
