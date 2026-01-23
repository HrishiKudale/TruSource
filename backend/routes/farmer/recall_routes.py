# backend/routes/farmer/recall_routes.py
from flask import Blueprint, session, request, jsonify
from backend.services.farmer.recall_service import RecallService

# MUST be named recall_bp for register_blueprints.py
recall_bp = Blueprint("farmer_recall", __name__, url_prefix="/api/recall")


@recall_bp.get("/notifications")
def recall_notifications():
    if session.get("role") != "farmer":
        return jsonify({"ok": False, "err": "unauthorized"}), 401

    farmer_id = session.get("user_id")
    span = request.args.get("span", default=2_000_000, type=int)
    fb = request.args.get("fromBlock", type=int)
    tb = request.args.get("toBlock", type=int)

    return RecallService.get_recall_events(
        farmer_id=farmer_id,
        span_blocks=span,
        from_block=fb,
        to_block=tb
    )
