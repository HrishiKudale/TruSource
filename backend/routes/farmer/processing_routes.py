# backend/routes/farmer/processing_routes.py

from flask import Blueprint, render_template, session, jsonify, redirect, request, url_for, flash

from backend.services.farmer.processing_service import FarmerProcessingService
from backend.services.farmer.crop_service import CropService
from backend.mongo import mongo

processing_bp = Blueprint(
    "farmer_processing_bp",
    __name__,
    url_prefix="/farmer/processing",
)


# ----------------- REQUEST PROCESSING PAGE (FORM) -----------------
@processing_bp.get("/request")
def request_processing_page():
    """Show Processing Request form."""
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]

    # manufacturers from users collection
    manufacturers = list(
        mongo.db.users.find(
            {"role": "manufacturer"},
            {"_id": 0, "userId": 1, "manufacturerId": 1, "name": 1, "location": 1},
        )
    )

    # crops for this farmer (from blockchain-backed CropService)
    crop_data = CropService.get_my_crops(farmer_id)
    crops = crop_data.get("crops", [])

    return render_template(
        "AddProcess.html",
        active_page="storage",
        active_submenu="processing",
        manufacturers=manufacturers,
        crops=crops,
        items=[],   # no prefilled table rows
    )


@processing_bp.post("/request")
def submit_request():
    """Handle POST from ProcessingRequest.html and write farmer_request docs."""
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]

    res = FarmerProcessingService.create_processing_requests(farmer_id, request.form)

    if not res.get("ok"):
        # re-render form with error message
        manufacturers = list(
            mongo.db.users.find(
                {"role": "manufacturer"},
                {"_id": 0, "userId": 1, "manufacturerId": 1, "name": 1, "location": 1},
            )
        )
        crop_data = CropService.get_my_crops(farmer_id)
        crops = crop_data.get("crops", [])

        return render_template(
            "AddProcess.html",
            active_page="storage",
            active_submenu="processing",
            manufacturers=manufacturers,
            crops=crops,
            items=[],
            error=res.get("error"),
        ), 400

    # success → go back to overview
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


# ----------------- HTML DETAIL -----------------
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


@processing_bp.get("/api/crop/<crop_id>")
def processing_detail_api(crop_id: str):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session["user_id"]
    return jsonify(FarmerProcessingService.get_processing_detail(farmer_id, crop_id))

# ----------------- MANUFACTURER / FACTORY INFO PAGE -----------------
@processing_bp.get("/manufacturer/<manufacturer_id>")
def manufacturer_info_page(manufacturer_id: str):
    """
    ProcessInfo page:
    - Main header: Manufacturer ID
    - Factory Details card
    - Table of all farmer_request docs for this manufacturer
    """
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