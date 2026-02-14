from flask import Blueprint, request, jsonify, render_template, session
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError

from backend.services.traceability.traceability_services import TraceabilityService

traceability_bp = Blueprint("traceability_bp", __name__, url_prefix="/farmer")


def _get_user_id_web_or_jwt():
    # 1) Web session
    if session.get("user_id"):
        return session.get("user_id")

    # 2) JWT (mobile)
    try:
        verify_jwt_in_request(optional=True)
        ident = get_jwt_identity() or {}
        # your auth uses identity = { userId, role, ... }
        user_id = ident.get("userId") or ident.get("user_id")
        return user_id
    except NoAuthorizationError:
        return None
    except Exception:
        return None


@traceability_bp.get("/api/traceability")
def traceability_api():
    """
    GET /farmer/api/traceability?q=<cropId|cropName>
    Supports cropId= cropName=
    Web: uses session
    Mobile: uses Bearer JWT
    """
    user_id = _get_user_id_web_or_jwt()
    if not user_id:
        return jsonify(ok=False, err="unauthorized"), 401

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
        crop_id=crop_id or None,
        crop_name=crop_name or None,
        user_id=user_id,
    )

    return jsonify(ok=True, data=vm.to_dict()), 200
