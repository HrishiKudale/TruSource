# backend/routes/farmer/dashboard_routes.py

from flask import Blueprint, redirect, render_template, request, session, jsonify, url_for

from backend.services.farmer.crop_service import CropService
from backend.services.farmer.dashboard_service import DashboardService

dashboard_bp = Blueprint(
    "farmer_dashboard_bp",
    __name__,
    url_prefix="/farmer/dashboard",
)

def _require_farmer():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return False, redirect(url_for("auth.new_login")), None
    farmer_id = session.get("user_id")
    if not farmer_id:
        return False, redirect(url_for("auth.new_login")), None
    return True, None, farmer_id


@dashboard_bp.get("/")
def dashboard_page():
    if session.get("role")!="farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session.get("user_id")
    # date filter from query (?till=YYYY-MM-DD)
    till = request.args.get("till")
    dashboard = DashboardService.build_dashboard(farmer_id, till_date=till)
    crop_data = CropService.get_my_crops(farmer_id)
    crops = crop_data.get("crops", [])
    return render_template(
        "farmer_dashboard.html",
        dashboard=dashboard,
        active_page="dashboard",
        active_submenu="dashboard",
        crops=crops
    )


@dashboard_bp.get("/data")
def dashboard_data_api():
    """
    AJAX endpoint if you want the page to refresh without reload.
    Usage: /farmer/dashboard/data?till=2026-01-10
    """
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return jsonify({"error": "unauthorized"}), 401

    till = request.args.get("till")
    dashboard = DashboardService.build_dashboard(farmer_id, till_date=till)
    return jsonify(dashboard), 200




@dashboard_bp.get("/api/farms")
def api_farms():
    # farmer auth
    if session.get("role") != "farmer":
        return jsonify({"error": "unauthorized"}), 401

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    crop_type = request.args.get("cropType")  # from dropdown (e.g. Wheat)
    crop_id = request.args.get("crop_id")     # optional

    farms = DashboardService.get_farm_polygons(user_id=user_id, crop_type=crop_type, crop_id=crop_id)

    return jsonify({
        "ok": True,
        "count": len(farms),
        "farms": farms
    }), 200
