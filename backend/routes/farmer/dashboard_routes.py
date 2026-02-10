# backend/routes/farmer/dashboard_routes.py

from flask import Blueprint, redirect, render_template, request, session, jsonify, url_for

from flask_jwt_extended import (
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
    """
    Returns farmer_id if authenticated as farmer via:
      1) Flask cookie session (web)
      2) JWT Bearer token (mobile)
    Otherwise returns None.
    """
    # 1) Web session auth
    if session.get("role") == "farmer" and session.get("user_id"):
        return session.get("user_id")

    # 2) JWT auth (mobile)
    try:
        verify_jwt_in_request(optional=True)  # does not raise if missing
        ident = get_jwt_identity() or {}
        role = (ident.get("role") or "").lower()
        user_id = ident.get("userId") or ident.get("user_id")
        if role == "farmer" and user_id:
            return user_id
        return None
    except NoAuthorizationError:
        return None
    except Exception:
        # don't crash API if token malformed
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
