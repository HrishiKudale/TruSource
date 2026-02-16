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
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError


@traceability_bp.get("/api/traceability")
def traceability_api():
    """
    GET /farmer/api/traceability?cropId=...
    Works for:
      - Web (session)
      - Mobile (JWT Bearer)
    """

    # 1️⃣ Web session support
    if session.get("role") == "farmer" and session.get("user_id"):
        user_id = session.get("user_id")
    else:
        # 2️⃣ JWT support
        try:
            verify_jwt_in_request(optional=True)
            ident = get_jwt_identity()

            if isinstance(ident, dict):
                role = (ident.get("role") or "").lower()
                user_id = ident.get("userId") or ident.get("user_id")
            else:
                user_id = None
                role = None

            if role != "farmer" or not user_id:
                return jsonify(ok=False, err="unauthorized"), 401

        except NoAuthorizationError:
            return jsonify(ok=False, err="auth"), 401
        except Exception as e:
            print("TRACE JWT ERROR:", e)
            return jsonify(ok=False, err="token_error"), 401

    # 🔎 Query params
    q = (request.args.get("q") or "").strip()
    crop_id = (request.args.get("cropId") or "").strip()
    crop_name = (request.args.get("cropName") or "").strip()

    if not crop_id and q:
        crop_id = q
    if not crop_name and q:
        crop_name = q

    if not crop_id and not crop_name:
        return jsonify(ok=False, err="q or cropId or cropName required"), 400

    vm = TraceabilityService.build_traceability(
        crop_id=crop_id,
        user_id=user_id
    )

    return jsonify(ok=True, data=vm.to_dict())
