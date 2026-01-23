from flask import Blueprint, request, jsonify, render_template, session

from backend.services.traceability.traceability_services import TraceabilityService

# If your blueprint is already url_prefix="/farmer", keep it.
# Example:
traceability_bp = Blueprint("traceability_bp", __name__, url_prefix="/farmer")


# ------------------------------
# PAGE (HTML) — NO crop_id needed
# ------------------------------
@traceability_bp.get("/traceability")
def traceability_page():
    """
    Renders Traceability.html.
    DOES NOT require crop_id.
    User will search from the search bar.
    """
    user_id = session.get("user_id")
    if not user_id:
        # redirect to login if you want
        return render_template("new_login.html"), 401

    return render_template("Traceability.html", active_page="traceability")


# -----------------------------------------
# OPTIONAL legacy route: /traceability/<id>
# (If you still want to support direct open)
# -----------------------------------------
@traceability_bp.get("/traceability/<crop_id>")
def traceability_page_with_crop(crop_id):
    """
    Renders page and pre-fills search via crop_id (optional).
    """
    user_id = session.get("user_id")
    if not user_id:
        return render_template("new_login.html"), 401

    return render_template("Traceability.html", crop_id=crop_id, active_page="traceability")


# ------------------------------
# API (JSON)
# ------------------------------
@traceability_bp.get("/api/traceability")
def traceability_api():
    """
    GET /farmer/api/traceability?q=<cropId|cropName>
    Also supports cropId= and cropName=
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(ok=False, err="auth"), 401

    q = (request.args.get("q") or "").strip()
    crop_id = (request.args.get("cropId") or "").strip()
    crop_name = (request.args.get("cropName") or "").strip()

    # allow q as cropId/cropName
    if not crop_id and q:
        crop_id = q
    if not crop_name and q:
        crop_name = q

    if not crop_id and not crop_name:
        return jsonify(ok=False, err="q or cropId or cropName required"), 400

    # IMPORTANT: build_traceability should accept crop_id OR crop_name and resolve internally
    vm = TraceabilityService.build_traceability(
        crop_id=crop_id,
        user_id=user_id
    )
    return jsonify(ok=True, data=vm.to_dict())
