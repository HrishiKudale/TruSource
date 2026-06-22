# backend/routes/trace_routes.py

from io import BytesIO

import qrcode
from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    session,
    send_file,
    url_for,
)
from flask_jwt_extended import (
    verify_jwt_in_request,
    get_jwt_identity,
    get_jwt,
)

from backend.services.traceability.traceability_services import TraceabilityService


traceability_bp = Blueprint(
    "traceability_bp",
    __name__,
    url_prefix="/farmer",
)


def _get_farmer_id_web_or_jwt():
    """
    Supports:
    1. Web session auth
    2. JWT auth for mobile/API
    """
    # 1) Web session auth
    if session.get("role") == "farmer" and session.get("user_id"):
        return session.get("user_id")

    # 2) JWT auth
    try:
        verify_jwt_in_request(optional=True)

        user_id = get_jwt_identity()
        claims = get_jwt() or {}
        role = (claims.get("role") or "").lower()

        if role == "farmer" and user_id:
            return user_id

        return None

    except Exception:
        return None


# ------------------------------
# PAGE: /farmer/traceability
# ------------------------------
@traceability_bp.get("/traceability")
def traceability_page():
    user_id = session.get("user_id")

    if not user_id:
        return render_template("newlogin.html"), 401

    crops = TraceabilityService.get_crops_for_user(user_id)

    return render_template(
        "Traceability.html",
        crops=crops,
        active_page="traceability",
    )


# ------------------------------
# OPTIONAL PAGE: /farmer/traceability/<crop_id>
# ------------------------------
@traceability_bp.get("/traceability/<crop_id>")
def traceability_page_with_crop(crop_id):
    user_id = session.get("user_id")

    if not user_id:
        return render_template("newlogin.html"), 401

    crops = TraceabilityService.get_crops_for_user(user_id)

    return render_template(
        "Traceability.html",
        crops=crops,
        crop_id=crop_id,
        active_page="traceability",
    )


# ------------------------------
# API: Get user's crops for dropdown/search
# GET /farmer/api/traceability/crops
# ------------------------------
@traceability_bp.get("/api/traceability/crops")
def traceability_crops_api():
    farmer_id = _get_farmer_id_web_or_jwt()

    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    crops = TraceabilityService.get_crops_for_user(farmer_id)

    return jsonify(
        ok=True,
        crops=crops,
    ), 200


# ------------------------------
# API: Build traceability by cropId
# GET /farmer/api/traceability?cropId=CR001
# ------------------------------
@traceability_bp.get("/api/traceability")
def traceability_api():
    farmer_id = _get_farmer_id_web_or_jwt()

    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    crop_id = (request.args.get("cropId") or "").strip()

    if not crop_id:
        return jsonify(ok=False, err="cropId required"), 400

    try:
        vm = TraceabilityService.build_traceability(
            crop_id=crop_id,
            user_id=farmer_id,
        )

        return jsonify(
            ok=True,
            data=vm.to_dict(),
        ), 200

    except ValueError as e:
        return jsonify(
            ok=False,
            err=str(e) or "not_found_or_unauthorized",
        ), 404

    except Exception as e:
        print("TRACEABILITY API ERROR:", e)
        return jsonify(
            ok=False,
            err="server_error",
        ), 500


# ------------------------------
# API: Generate QR PNG
# POST /farmer/api/traceability/<crop_id>/qr
# ------------------------------
@traceability_bp.post("/api/traceability/<crop_id>/qr")
def generate_crop_qr(crop_id):
    farmer_id = _get_farmer_id_web_or_jwt()

    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    try:
        token = TraceabilityService.get_or_create_public_token(
            crop_id=crop_id,
            user_id=farmer_id,
        )
    except ValueError:
        return jsonify(ok=False, err="not_found_or_unauthorized"), 404

    public_url = url_for(
        "public_trace_bp.public_traceability",
        token=token,
        _external=True,
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(public_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(
        buf,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{crop_id}_traceability_qr.png",
    )


# ------------------------------
# API: Get public link
# GET /farmer/api/traceability/<crop_id>/public-link
# ------------------------------
@traceability_bp.get("/api/traceability/<crop_id>/public-link")
def get_public_link(crop_id):
    farmer_id = _get_farmer_id_web_or_jwt()

    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    try:
        token = TraceabilityService.get_or_create_public_token(
            crop_id=crop_id,
            user_id=farmer_id,
        )
    except ValueError:
        return jsonify(ok=False, err="not_found_or_unauthorized"), 404

    public_url = url_for(
        "public_trace_bp.public_traceability",
        token=token,
        _external=True,
    )

    return jsonify(
        ok=True,
        token=token,
        url=public_url,
    ), 200


# ------------------------------
# API: Demo QR
# GET /farmer/api/traceability/<crop_id>/demo-qr
# ------------------------------
@traceability_bp.get("/api/traceability/<crop_id>/demo-qr")
def demo_qr(crop_id):
    farmer_id = _get_farmer_id_web_or_jwt()

    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    public_url = url_for(
        "public_demo_bp.public_demo_traceability",
        crop_id=crop_id,
        _external=True,
    )

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(public_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(
        buf,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{crop_id}_DEMO_traceability_qr.png",
    )