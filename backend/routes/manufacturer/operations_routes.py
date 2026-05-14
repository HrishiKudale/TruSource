# backend/routes/manufacturer/crop_routes.py
import json
from flask import Blueprint, redirect, render_template, request, session, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request
from backend.blockchain import get_user_crops
from backend.services.farmer.crop_service import CropService
from backend.mongo import mongo

from backend.mongo_safe import get_db


# ======================================================
# 1) MAIN CROP BLUEPRINT  →  /manufacturer/crop/*
# ======================================================
operations_bp = Blueprint("manufacturer_crop_bp", __name__, url_prefix="/manufacturer/crop")


# ------------------  MY CROPS (HTML) ------------------
@operations_bp.get("/my")
def my_crops_page():
    if session.get("role") != "manufacturer":
        return jsonify({"error": "unauthorized"}), 401

    manufacturer_id = session["user_id"]
    crops = CropService.get_my_crops(manufacturer_id)

    return render_template(
        "MyCrop.html",
        crops=crops,
        active_page="my_crops",
        active_submenu=None

    )


@operations_bp.get("/myoperations")
def my_operations():
    if session.get("role") != "manufacturer" or not session.get("user_id"):
        return redirect("/newlogin")

    manufacturer_id = session["user_id"]
    data = CropService.get_my_crops(manufacturer_id)

    return render_template(
        "manufacturer/Myoperations.html",
        active_page="operations",
        active_submenu=None,
        crops=data["crops"],
        total_crops=data["total_crops"],
        total_area_acres=data["total_area_acres"],
        total_harvest_qtl=data["total_harvest_qtl"],
        total_sold_qtl=data["total_sold_qtl"],
    )
def _get_manufacturer_id_web_or_jwt():
    # 1) Web session auth
    if session.get("role") == "manufacturer" and session.get("user_id"):
        return session.get("user_id")

    # 2) JWT auth (mobile)
    try:
        verify_jwt_in_request(optional=True)

        user_id = get_jwt_identity()   # ✅ string now
        claims = get_jwt() or {}
        role = (claims.get("role") or "").lower()

        if role == "manufacturer" and user_id:
            return user_id
        return None
    except Exception:
        return None

# ------------------  MY CROPS (JSON) ------------------
from flask import jsonify
# make sure verify_jwt_in_request/get_jwt_identity/get_jwt are imported where _get_manufacturer_id_web_or_jwt lives

@operations_bp.get("/api/myoperations")
def my_crops_api():
    manufacturer_id = _get_manufacturer_id_web_or_jwt()
    if not manufacturer_id:
        return jsonify(ok=False, err="auth"), 401

    data = CropService.get_my_crops(manufacturer_id)

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
@operations_bp.get("/crop/<crop_id>")
def crop_info_page(crop_id: str):
    if session.get("role") != "manufacturer" or not session.get("user_id"):
        return redirect("/newlogin")

    manufacturer_id = session["user_id"]
    crop = CropService.get_crop_detail(manufacturer_id, crop_id)

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
    
    activities = CropService.get_crop_activity_timeline(manufacturer_id, crop_id)

    print("✅ activities count:", len(activities or []))  # DEBUG

    return render_template(
        "CropInfo.html",
        crop=crop,
        coords=coords,
        activities=activities,
        active_page="my_crops"

    )


# ------------------  CROP DETAIL (JSON) ------------------
@operations_bp.get("/api/crop/<crop_id>")
def crop_info_api(crop_id: str):
    manufacturer_id = _get_manufacturer_id_web_or_jwt()
    if not manufacturer_id:
        return jsonify(ok=False, err="auth"), 401

    data = CropService.get_crop_detail(manufacturer_id,crop_id)
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
    
    activities = CropService.get_crop_activity_timeline(manufacturer_id, crop_id)

    print("✅ activities count:", len(activities or []))  # DEBUG
    return jsonify(
        ok=True,
        data={
            "data": data,
            "coords":coords,
            "activities":activities
        },
    ), 200



# ------------------  ADD CROP PAGE ------------------

@operations_bp.get("/crop/add")
def add_crop_blank():
    if session.get("role") != "manufacturer":
        return redirect("/newlogin")

    return render_template(
        "AddCrop.html",
        active_page="my_crops",
        mode="register_crop",   # ✅ explicit mode
        crop=None,
        coords=[]
    )


@operations_bp.get("/add/<crop_id>")
def add_crop_page(crop_id: str):
    if session.get("role") != "manufacturer" or not session.get("user_id"):
        return redirect("/newlogin")

    manufacturer_id = session["user_id"]
    crop = CropService.get_crop_detail(manufacturer_id, crop_id)
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


# ------------------  REGISTER CROP (CHAIN + MONGO) ------------------
@operations_bp.post("/register")
def register_crop_api():
    manufacturer_id = _get_manufacturer_id_web_or_jwt()  # ✅ use same auth
    if not manufacturer_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    raw = request.get_json(silent=True) if request.is_json else request.form.to_dict()

    if isinstance(raw.get("coordinates"), str):
        try:
            raw["coordinates"] = json.loads(raw["coordinates"])
        except:
            pass

    try:
        res = CropService.register_crop_with_blockchain(
            manufacturer_id=manufacturer_id,   # ✅ use manufacturer_id from jwt
            payload=raw,
        )
        return jsonify(res), (200 if res.get("ok") else 400)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

