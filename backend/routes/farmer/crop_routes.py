# backend/routes/farmer/crop_routes.py
import json
from flask import Blueprint, redirect, render_template, request, session, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request
from backend.blockchain import get_user_crops
from backend.services.farmer.crop_service import CropService
from backend.mongo import mongo
from backend.services.farmer.harvest_service import HarvestService
from backend.mongo_safe import get_db


# ======================================================
# 1) MAIN CROP BLUEPRINT  →  /farmer/crop/*
# ======================================================
crop_bp = Blueprint("farmer_crop_bp", __name__, url_prefix="/farmer/crop")


# ------------------  MY CROPS (HTML) ------------------
@crop_bp.get("/my")
def my_crops_page():
    if session.get("role") != "farmer":
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session["user_id"]
    crops = CropService.get_my_crops(farmer_id)

    return render_template(
        "MyCrop.html",
        crops=crops,
        active_page="my_crops",
        active_submenu=None

    )


@crop_bp.get("/mycrop")
def my_crops():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    data = CropService.get_my_crops(farmer_id)

    return render_template(
        "Mycrop.html",
        active_page="my_crops",
        active_submenu=None,
        crops=data["crops"],
        total_crops=data["total_crops"],
        total_area_acres=data["total_area_acres"],
        total_harvest_qtl=data["total_harvest_qtl"],
        total_sold_qtl=data["total_sold_qtl"],
    )
def _get_farmer_id_web_or_jwt():
    # 1) Web session auth
    if session.get("role") == "farmer" and session.get("user_id"):
        return session.get("user_id")

    # 2) JWT auth (mobile)
    try:
        verify_jwt_in_request(optional=True)

        user_id = get_jwt_identity()   # ✅ string now
        claims = get_jwt() or {}
        role = (claims.get("role") or "").lower()

        if role == "farmer" and user_id:
            return user_id
        return None
    except Exception:
        return None

# ------------------  MY CROPS (JSON) ------------------
from flask import jsonify
# make sure verify_jwt_in_request/get_jwt_identity/get_jwt are imported where _get_farmer_id_web_or_jwt lives

@crop_bp.get("/api/mycrop")
def my_crops_api():
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    data = CropService.get_my_crops(farmer_id)

    return jsonify(
        ok=True,
        data={
            "crops": data["crops"],
            "total_crops": data["total_crops"],
            "total_area_acres": data["total_area_acres"],
            "total_harvest_qtl": data["total_harvest_qtl"],
            "total_sold_qtl": data["total_sold_qtl"],
        },
    ), 200

# ------------------  CROP DETAIL (HTML) ------------------
@crop_bp.get("/crop/<crop_id>")
def crop_info_page(crop_id: str):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    crop = CropService.get_crop_detail(farmer_id, crop_id)

    # fetch coordinates for THIS crop
    db = get_db()

    coord_doc = None
    if db is not None:
        coord_doc = db.farm_coordinates.find_one(
            {"crop_id": crop_id},
            sort=[("created_at", -1)]
        )
    else:
        print("⚠️ Mongo disabled/unavailable: skipping farm_coordinates lookup")

    coords = coord_doc["coordinates"] if coord_doc else []
    
    activities = CropService.get_crop_activity_timeline(farmer_id, crop_id)

    print("✅ activities count:", len(activities or []))  # DEBUG

    return render_template(
        "CropInfo.html",
        crop=crop,
        coords=coords,
        activities=activities,
        active_page="my_crops"

    )


# ------------------  CROP DETAIL (JSON) ------------------
@crop_bp.get("/api/crop/<crop_id>")
def crop_info_api(crop_id: str):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    data = CropService.get_my_crops(farmer_id,crop_id)
    return jsonify(
        ok=True,
        data={
            "data": data,
        },
    ), 200



# ------------------  ADD CROP PAGE ------------------

@crop_bp.get("/crop/add")
def add_crop_blank():
    if session.get("role") != "farmer":
        return redirect("/newlogin")

    return render_template(
        "AddCrop.html",
        active_page="my_crops",
        mode="register_crop",   # ✅ explicit mode
        crop=None,
        coords=[]
    )


@crop_bp.get("/add/<crop_id>")
def add_crop_page(crop_id: str):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    crop = CropService.get_crop_detail(farmer_id, crop_id)
    db= get_db()
    coord_doc = None
    if db is not None:
        coord_doc = mongo.db.farm_coordinates.find_one(
            {"crop_id": crop_id},
            {"_id": 0, "coordinates": 1}
        )
        coords = coord_doc["coordinates"] if coord_doc else []

    return render_template(
        "AddCrop.html",
        active_page="my_crops",
        mode="register_harvest",  # ✅ explicit mode
        crop=crop,
        coords=coords
    )
@crop_bp.post("/harvest/register")
def register_harvest_api():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()

    # Accept both cropId and crop_id
    crop_id = (payload.get("crop_id") or payload.get("cropId") or "").strip()
    if not crop_id:
        return jsonify({"ok": False, "error": "crop_id is required"}), 400

    try:
        # (Optional) validate crop belongs to farmer (recommended)
        farmer_id = session["user_id"]
        crop = CropService.get_crop_detail(farmer_id, crop_id)  # <-- NOTE signature
        if not crop:
            return jsonify({"ok": False, "error": "Crop not found"}), 404

        res = HarvestService.register_harvest_with_blockchain(
            farmer_id=farmer_id,
            payload=payload
        )
        return jsonify(res), (200 if res.get("ok") else 400)

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ------------------  REGISTER CROP (CHAIN + MONGO) ------------------
@crop_bp.post("/register")
def register_crop_api():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    raw = request.get_json(silent=True) if request.is_json else request.form.to_dict()

    # coordinates may be JSON string
    if isinstance(raw.get("coordinates"), str):
        try:
            raw["coordinates"] = json.loads(raw["coordinates"])
        except:
            pass

    try:
        res = CropService.register_crop_with_blockchain(
            farmer_id=session["user_id"],
            payload=raw,
        )
        return jsonify(res), (200 if res.get("ok") else 400)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



# ======================================================
# 2) SEPARATE BLUEPRINT → /farmer/*
#    Needed for map JS calls
# ======================================================
# farm_coord_routes.py
from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from typing import Optional

farm_coord_bp = Blueprint("farm_coord_bp", __name__, url_prefix="/farmer")

def _get_farmer_id_web_or_jwt() -> Optional[str]:
    # Web session auth
    if session.get("role") == "farmer" and session.get("user_id"):
        return session.get("user_id")

    # JWT auth (mobile)
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()  # string
        claims = get_jwt() or {}
        role = (claims.get("role") or "").lower()

        if role == "farmer" and user_id:
            return user_id
        return None
    except Exception:
        return None


@farm_coord_bp.post("/api/save_farm_coordinates")
def save_farm_coordinates_api():
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    payload = request.get_json(silent=True) or {}

    # expected payload:
    # {
    #   "name": "Farm 1",
    #   "polygon": [{"latitude":..,"longitude":..}, ...],
    #   "area_acres": 1.23,
    #   "center": {"latitude":..,"longitude":..}
    # }

    result = CropService.save_coordinates_only(
        farmer_id=farmer_id,
        payload=payload
    )

    # result should include farmId or polygonId for next step
    return jsonify(ok=True, data=result), 200



# ------------------  GET COORDINATES ------------------
@farm_coord_bp.get("/get_farm_coordinates")
def get_farm_coordinates():
    if session.get("role") != "farmer":
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    farmer_id = session["user_id"]
    db= get_db()
    coord_doc= None
    if db is not None:
        coord_doc = list(
            mongo.db.farm_coordinates.find({"user_id": farmer_id}, {"_id": 0})
        )

    return jsonify({"ok": True, "data": coord_doc})
