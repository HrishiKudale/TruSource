# backend/rfid_routes.py
from flask import Blueprint, current_app, request, jsonify, session
from backend.services.rfid.rfid_services import register_epcs_onchain, fetch_rfid_list, fetch_rfid_details, normalize_epc
from backend.mongo import mongo

rfid_bp = Blueprint("rfid_bp", __name__, url_prefix="/rfid")

@rfid_bp.post("/register")
def register_rfid():
    user_id = session.get("user_id")
    print("SESSION user_id:", user_id)
    if not user_id:
        return jsonify(ok=False, message="auth"), 401

    # Fetch user from Mongo
    user = mongo.db.users.find_one({"userId": user_id})
    print("MONGO user:", user)
    if not user:
        return jsonify(ok=False, message="User not found"), 404

    username = user.get("name", "")
    print("USERNAME fetched:", username)

    data = request.get_json(silent=True) or {}
    data["userId"] = user_id
    data["username"] = username

    ok, msg, meta = register_epcs_onchain(data)
    if not ok:
        return jsonify(ok=False, message=msg), 400
    return jsonify(ok=True, message=msg, **meta)





@rfid_bp.get("/list")
def list_epcs():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(ok=False, message="auth"), 401

    crop_id = (request.args.get("cropId") or "").strip()
    if not crop_id:
        return jsonify(ok=False, message="cropId required"), 400

    epcs = fetch_rfid_list(crop_id)
    return jsonify(ok=True, cropId=crop_id, items=epcs, count=len(epcs))

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

    rec = fetch_rfid_details(crop_id, epc)
    if not rec:
        return jsonify(ok=False, message="not_found"), 404

    # Solidity returns tuple in same order as getRFID
    return jsonify(ok=True, cropId=crop_id, epc=epc, record={
        "userId": rec[0],
        "username": rec[1],
        "cropType": rec[2],
        "cropId": rec[3],
        "packagingDate": rec[4],
        "expiryDate": rec[5],
        "bagCapacity": rec[6],
        "totalBags": rec[7],
        "rfidEPC": rec[8],
        "timestamp": int(rec[9]),
    })
