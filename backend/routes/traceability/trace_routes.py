from flask import Blueprint, request, jsonify, render_template, session

from backend.services.traceability.traceability_services import TraceabilityService

# If your blueprint is already url_prefix="/farmer", keep it.
# Example:
traceability_bp = Blueprint("traceability_bp", __name__, url_prefix="/farmer")


# ------------------------------
# PAGE (HTML) — NO crop_id needed
# ------------------------------
# backend/routes/traceability_routes.py (or wherever your blueprint is)

from backend.services.traceability.traceability_services import TraceabilityService

@traceability_bp.get("/traceability")
def traceability_page():
    """
    Renders Traceability.html.
    DOES NOT require crop_id.
    User will search from the search bar.
    """
    user_id = session.get("user_id")
    if not user_id:
        return render_template("newlogin.html"), 401

    # Fetch crops for this user
    crops = TraceabilityService.get_crops_for_user(user_id)

    return render_template(
        "Traceability.html",
        crops=crops,
        active_page="traceability"
    )

# -----------------------------------------
# OPTIONAL legacy route: /traceability/<id>
# (If you still want to support direct open)
# -----------------------------------------
@traceability_bp.get("/traceability/<crop_id>")
def traceability_page_with_crop(crop_id):
    user_id = session.get("user_id")
    if not user_id:
        return render_template("new_login.html"), 401

    crops = TraceabilityService.get_crops_for_user(user_id)

    return render_template(
        "Traceability.html",
        crops=crops,
        crop_id=crop_id,  # preselect this crop
        active_page="traceability"
    )
# ------------------------------
# API (JSON)
# ------------------------------
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from flask_jwt_extended.exceptions import NoAuthorizationError

@traceability_bp.get("/api/traceability")
def traceability_api():
    # 1) Web session support
    if session.get("role") == "farmer" and session.get("user_id"):
        user_id = session.get("user_id")

    else:
        # 2) JWT support
        try:
            verify_jwt_in_request()  # <-- require token here (not optional)
            user_id = get_jwt_identity()  # <-- string userId
            claims = get_jwt() or {}
            role = (claims.get("role") or "").lower()

            if role != "farmer" or not user_id:
                return jsonify(ok=False, err="unauthorized"), 401

        except NoAuthorizationError:
            return jsonify(ok=False, err="auth"), 401
        except Exception as e:
            print("TRACE JWT ERROR:", e)
            return jsonify(ok=False, err="token_error"), 401

    crop_id = (request.args.get("cropId") or "").strip()
    if not crop_id:
        return jsonify(ok=False, err="cropId required"), 400

    vm = TraceabilityService.build_traceability(crop_id=crop_id, user_id=user_id)
    return jsonify(ok=True, data=vm.to_dict()), 200



# in your existing traceability_bp file
from flask import send_file, url_for
from io import BytesIO
import qrcode

@traceability_bp.post("/api/traceability/<crop_id>/qr")
def generate_crop_qr(crop_id):
    """
    Farmer-only: returns QR code PNG for this crop (batch-level).
    QR encodes public URL: /t/<token>
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(ok=False, err="unauthorized"), 401

    # 1) get/create token
    try:
        token = TraceabilityService.get_or_create_public_token(crop_id=crop_id, user_id=user_id)
    except ValueError:
        return jsonify(ok=False, err="not_found_or_unauthorized"), 404

    # 2) build absolute public URL
    public_url = url_for("public_trace_bp.public_traceability", token=token, _external=True)

    # 3) generate QR image
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(public_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # 4) return as PNG
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(
        buf,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{crop_id}_traceability_qr.png",
    )

@traceability_bp.get("/api/traceability/<crop_id>/public-link")
def get_public_link(crop_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(ok=False, err="unauthorized"), 401

    try:
        token = TraceabilityService.get_or_create_public_token(crop_id=crop_id, user_id=user_id)
    except ValueError:
        return jsonify(ok=False, err="not_found_or_unauthorized"), 404

    public_url = url_for("public_trace_bp.public_traceability", token=token, _external=True)
    return jsonify(ok=True, token=token, url=public_url)



from flask import url_for, send_file
from io import BytesIO
import qrcode

@traceability_bp.get("/api/traceability/<crop_id>/demo-qr")
def demo_qr(crop_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(ok=False, err="unauthorized"), 401

    public_url = url_for("public_demo_bp.public_demo_traceability", crop_id=crop_id, _external=True)

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
