# backend/routes/farmer/processing_routes.py

from flask import Blueprint, render_template, session, jsonify, redirect, request, url_for, flash

from backend.mongo_safe import get_col
from backend.services.farmer.processing_service import FarmerProcessingService
from backend.services.farmer.crop_service import CropService

processing_bp = Blueprint(
    "farmer_processing_bp",
    __name__,
    url_prefix="/farmer/processing",
)

# ----------------- REQUEST PROCESSING PAGE (FORM) -----------------
@processing_bp.get("/request")
def request_processing_page():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]

    users_col = get_col("users")
    manufacturers = []
    mongo_error = None

    if users_col is not None:
        manufacturers = list(
            users_col.find(
                {"role": "manufacturer"},
                {"_id": 0, "userId": 1, "manufacturerId": 1, "name": 1, "officeName": 1, "location": 1},
            )
        )
    else:
        mongo_error = "Mongo is disabled/unavailable. Manufacturer list cannot be loaded."

    crop_data = CropService.get_my_crops(farmer_id)
    crops = crop_data.get("crops", [])

    return render_template(
        "AddProcess.html",
        active_page="storage",
        active_submenu="processing",
        manufacturers=manufacturers,
        crops=crops,
        items=[],
        error=mongo_error,
    )


@processing_bp.post("/request")
def submit_request():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]

    res = FarmerProcessingService.create_processing_requests(farmer_id, request.form)

    if not res.get("ok"):
        # Re-render form with error message
        users_col = get_col("users")
        manufacturers = []
        mongo_error = res.get("error") or "Failed to submit processing request."

        if users_col is not None:
            manufacturers = list(
                users_col.find(
                    {"role": "manufacturer"},
                    {"_id": 0, "userId": 1, "manufacturerId": 1, "name": 1, "officeName": 1, "location": 1},
                )
            )
        else:
            if "Mongo" not in mongo_error:
                mongo_error = "Mongo is disabled/unavailable. Manufacturer list cannot be loaded."

        crop_data = CropService.get_my_crops(farmer_id)
        crops = crop_data.get("crops", [])

        return render_template(
            "AddProcess.html",
            active_page="storage",
            active_submenu="processing",
            manufacturers=manufacturers,
            crops=crops,
            items=[],
            error=mongo_error,
        ), 400

    flash("Processing request submitted.", "success")
    return redirect(url_for("farmer_processing_bp.processing_overview"))

# ----------------- HTML OVERVIEW -----------------
@processing_bp.get("/overview")
def processing_overview():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    data = FarmerProcessingService.get_processing_overview(farmer_id)

    return render_template(
        "ProcessingOverview.html",
        active_page="storage",
        active_submenu="processing",
        **data,
    )

# ----------------- NEW: REQUEST DETAIL (1 request -> items[]) -----------------
@processing_bp.get("/request/<request_id>")
def processing_request_detail(request_id: str):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    data = FarmerProcessingService.get_processing_request_detail(farmer_id, request_id)

    # Create this template later (or I can generate it for you)
    return render_template(
        "ProcessingRequestDetail.html",
        active_page="storage",
        active_submenu="processing",
        **data,
    )

# ----------------- LEGACY: HTML DETAIL BY CROP -----------------
@processing_bp.get("/crop/<crop_id>")
def processing_detail(crop_id: str):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    data = FarmerProcessingService.get_processing_detail(farmer_id, crop_id)

    return render_template(
        "ProcessingDetail.html",
        active_page="storage",
        active_submenu="processing",
        **data,
    )

# ----------------- JSON APIs -----------------
@processing_bp.get("/api/overview")
def processing_overview_api():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session["user_id"]
    return jsonify(FarmerProcessingService.get_processing_overview(farmer_id))

@processing_bp.get("/api/request/<request_id>")
def processing_request_detail_api(request_id: str):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session["user_id"]
    return jsonify(FarmerProcessingService.get_processing_request_detail(farmer_id, request_id))

@processing_bp.get("/api/crop/<crop_id>")
def processing_detail_api(crop_id: str):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session["user_id"]
    return jsonify(FarmerProcessingService.get_processing_detail(farmer_id, crop_id))

# ----------------- MANUFACTURER / FACTORY INFO PAGE -----------------
@processing_bp.get("/manufacturer/<manufacturer_id>")
def manufacturer_info_page(manufacturer_id: str):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    data = FarmerProcessingService.get_manufacturer_info(farmer_id, manufacturer_id)

    return render_template(
        "ProcessInfo.html",
        active_page="storage",
        active_submenu="processing",
        **data,
    )
