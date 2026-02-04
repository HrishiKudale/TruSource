# backend/rfid_routes.py

from flask import Blueprint, request, jsonify, session

from backend.mongo import mongo
from backend.services.rfid.rfid_services import RFIDService  
from backend.models.rfid.rfid_models import normalize_epc

rfid_bp = Blueprint("rfid_bp", __name__, url_prefix="/rfid")


def _get_authed_user():
    """
    Returns (user_id, username) or (None, None, response_tuple)
    """
    user_id = session.get("user_id")
    if not user_id:
        return None, None, (jsonify(ok=False, message="auth"), 401)

    user = mongo.db.users.find_one({"userId": user_id})
    if not user:
        return None, None, (jsonify(ok=False, message="User not found"), 404)

    username = (user.get("name") or user.get("username") or "").strip()
    if not username:
        username = "Farmer"

    return user_id, username, None


# ------------------------------------------------------------
# AUTO REGISTER (single OR bulk)
# Body supports either:
#   { epc: "...." }   OR   { epcs: ["..",".."] }
# ------------------------------------------------------------
@rfid_bp.post("/register")
def register_rfid_auto():
    user_id, username, err = _get_authed_user()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    data["userId"] = user_id
    data["username"] = username

    try:
        out = RFIDService.register_auto(data)

        # if service returned ok False, treat as 400 (validation/flow error)
        if not out.get("ok"):
            return jsonify(ok=False, message=out.get("err") or out.get("message") or "failed", **out), 400

        return jsonify(ok=True, message="RFID registered", **out), 200

    except Exception as e:
        return jsonify(ok=False, message="server_error", error=str(e)), 500


# ------------------------------------------------------------
# SINGLE REGISTER
# Body: { epc: "....", ... }
# ------------------------------------------------------------
@rfid_bp.post("/register-single")
def register_rfid_single():
    user_id, username, err = _get_authed_user()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    data["userId"] = user_id
    data["username"] = username

    # normalize early (optional but helpful)
    epc_raw = (data.get("epc") or "").strip()
    epc = normalize_epc(epc_raw)
    if not epc:
        return jsonify(ok=False, message="bad_epc"), 400
    data["epc"] = epc

    try:
        out = RFIDService.register_single_epc(data)
        if not out.get("ok"):
            return jsonify(ok=False, message=out.get("err") or out.get("error") or "failed", **out), 400
        return jsonify(ok=True, message="RFID registered", **out), 200
    except Exception as e:
        return jsonify(ok=False, message="server_error", error=str(e)), 500


# ------------------------------------------------------------
# BULK REGISTER
# Body: { epcs: ["..",".."], ... }
# ------------------------------------------------------------
@rfid_bp.post("/register-bulk")
def register_rfid_bulk():
    user_id, username, err = _get_authed_user()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    data["userId"] = user_id
    data["username"] = username

    epcs = data.get("epcs")
    if not isinstance(epcs, list) or not epcs:
        return jsonify(ok=False, message="epcs must be a non-empty list"), 400

    # normalize all EPCs (optional but useful; service also validates)
    cleaned = []
    for raw in epcs:
        c = normalize_epc(str(raw))
        if not c:
            return jsonify(ok=False, message=f"bad_epc: {raw}"), 400
        cleaned.append(c)
    data["epcs"] = cleaned

    try:
        out = RFIDService.register_epc_list(data)
        # bulk can return ok False but with partial successes (fallback case)
        # so we still return 200 and let UI read results
        if not out.get("ok") and out.get("results"):
            return jsonify(ok=True, message=out.get("note") or "partial_success", **out), 200

        if not out.get("ok"):
            return jsonify(ok=False, message=out.get("err") or out.get("error") or "failed", **out), 400

        return jsonify(ok=True, message="RFIDs registered", **out), 200

    except Exception as e:
        return jsonify(ok=False, message="server_error", error=str(e)), 500


# ------------------------------------------------------------
# LIST (Mongo)
# GET /rfid/list?cropId=...
# ------------------------------------------------------------
@rfid_bp.get("/list")
def list_rfids():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(ok=False, message="auth"), 401

    crop_id = (request.args.get("cropId") or "").strip()
    if not crop_id:
        return jsonify(ok=False, message="cropId required"), 400

    try:
        out = RFIDService.fetch_rfid_list(crop_id)
        if not out.get("ok"):
            return jsonify(ok=False, message=out.get("err") or "failed", **out), 400

        records = out.get("records") or []
        return jsonify(ok=True, cropId=crop_id, items=records, count=len(records)), 200

    except Exception as e:
        return jsonify(ok=False, message="server_error", error=str(e)), 500


# ------------------------------------------------------------
# DETAIL (Mongo + optional chain)
# GET /rfid/detail?cropId=...&epc=...
# ------------------------------------------------------------
@rfid_bp.get("/detail")
def rfid_detail():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(ok=False, message="auth"), 401

    crop_id = (request.args.get("cropId") or "").strip()
    epc_raw = (request.args.get("epc") or "").strip()
    epc = normalize_epc(epc_raw)

    if not crop_id:
        return jsonify(ok=False, message="cropId required"), 400
    if not epc:
        return jsonify(ok=False, message="bad_epc"), 400

    try:
        out = RFIDService.fetch_rfid_details(crop_id, epc)
        if not out.get("ok"):
            return jsonify(ok=False, message=out.get("err") or "failed", **out), 400

        # out = { ok, cropId, rfidEPC, mongo, chain }
        return jsonify(ok=True, **out), 200

    except Exception as e:
        return jsonify(ok=False, message="server_error", error=str(e)), 500
