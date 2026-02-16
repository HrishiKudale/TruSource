# backend/routes/farmer/dashboard_routes.py

from flask import Blueprint, redirect, render_template, request, session, jsonify, url_for

from flask_jwt_extended import (
    get_jwt,
    verify_jwt_in_request,
    get_jwt_identity
)
from flask_jwt_extended.exceptions import NoAuthorizationError

from backend.services.farmer.crop_service import CropService
from backend.services.farmer.dashboard_service import DashboardService

dashboard_bp = Blueprint(
    "farmer_dashboard_bp",
    __name__,
    url_prefix="/farmer/dashboard",
)

# ----------------------------
# HYBRID AUTH HELPERS
# ----------------------------


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



def _require_farmer_web_page():
    """
    Web-only gate for HTML pages that rely on session.
    """
    if session.get("role") != "farmer" or not session.get("user_id"):
        return False, redirect(url_for("auth.newlogin")), None  # your existing route
    farmer_id = session.get("user_id")
    if not farmer_id:
        return False, redirect(url_for("auth.newlogin")), None
    return True, None, farmer_id


# ----------------------------
# PAGES (WEB)
# ----------------------------
@dashboard_bp.get("/")
def dashboard_page():
    ok, resp, farmer_id = _require_farmer_web_page()
    if not ok:
        return resp

    till = request.args.get("till")  # ?till=YYYY-MM-DD
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


# ----------------------------
# APIs (WEB AJAX + MOBILE)
# ----------------------------
@dashboard_bp.get("/data")
def dashboard_data_api():
    """
    Works for:
      - Web (session)
      - Mobile (Bearer token)
    Usage: /farmer/dashboard/data?till=2026-01-10
    """
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify({"error": "unauthorized"}), 401

    till = request.args.get("till")
    dashboard = DashboardService.build_dashboard(farmer_id, till_date=till)
    return jsonify(dashboard), 200


@dashboard_bp.get("/api/farms")
def api_farms():
    """
    Works for:
      - Web (session)
      - Mobile (Bearer token)
    """
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify({"error": "unauthorized"}), 401

    crop_type = request.args.get("cropType")  # from dropdown (e.g. Wheat)
    crop_id = request.args.get("crop_id")     # optional

    farms = DashboardService.get_farm_polygons(
        user_id=farmer_id,
        crop_type=crop_type,
        crop_id=crop_id
    )

    return jsonify({
        "ok": True,
        "count": len(farms),
        "farms": farms
    }), 200


@dashboard_bp.get("/debug/jwt")
def debug_jwt():
    try:
        verify_jwt_in_request()  # NOT optional
        return jsonify(ok=True, identity=get_jwt_identity(), claims=get_jwt()), 200
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 401
