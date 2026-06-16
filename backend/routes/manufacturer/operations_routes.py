import json
from typing import Optional

from flask import Blueprint, redirect, render_template, request, session, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from backend.services.manufacturer.operations_service import OperationService


operations_bp = Blueprint(
    "manufacturer_operations_bp",
    __name__,
    url_prefix="/manufacturer/operations",
)


def _get_manufacturer_id_web_or_jwt() -> Optional[str]:
    if session.get("role") == "manufacturer" and session.get("user_id"):
        return session.get("user_id")

    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        claims = get_jwt() or {}
        role = (claims.get("role") or "").lower()

        if role == "manufacturer" and user_id:
            return user_id

        return None
    except Exception:
        return None


# HTML: /manufacturer/operations/my
@operations_bp.get("/my")
@operations_bp.get("/myoperations")
def my_operations_page():
    manufacturer_id = _get_manufacturer_id_web_or_jwt()

    if not manufacturer_id:
        return redirect("/newlogin")

    data = OperationService.get_my_operations(manufacturer_id)

    return render_template(
        "manufacturer/Myoperations.html",
        active_page="operations",
        active_submenu=None,
        products=data.get("products", []),
        total_products=data.get("total_products", 0),
        requested_products=data.get("requested_products", 0),
        active_operations=data.get("active_operations", 0),
        processed_operations=data.get("processed_operations", 0),
    )


# JSON: /manufacturer/operations/api/my
@operations_bp.get("/api/my")
@operations_bp.get("/api/myoperations")
def my_operations_api():
    manufacturer_id = _get_manufacturer_id_web_or_jwt()

    if not manufacturer_id:
        return jsonify(ok=False, err="auth"), 401

    data = OperationService.get_my_operations(manufacturer_id)
    return jsonify(ok=True, data=data), 200


# HTML detail
@operations_bp.get("/<operation_id>")
def operation_info_page(operation_id: str):
    manufacturer_id = _get_manufacturer_id_web_or_jwt()

    if not manufacturer_id:
        return redirect("/newlogin")

    operation = OperationService.get_operation_detail(
        manufacturer_id=manufacturer_id,
        operation_id=operation_id,
    )

    return render_template(
        "manufacturer/OperationInfo.html",
        operation=operation,
        active_page="operations",
        active_submenu=None,
    )


# JSON detail
@operations_bp.get("/api/<operation_id>")
def operation_info_api(operation_id: str):
    manufacturer_id = _get_manufacturer_id_web_or_jwt()

    if not manufacturer_id:
        return jsonify(ok=False, err="auth"), 401

    operation = OperationService.get_operation_detail(
        manufacturer_id=manufacturer_id,
        operation_id=operation_id,
    )

    return jsonify(
        ok=True,
        data={"operation": operation},
    ), 200


# Add operation page
@operations_bp.get("/add")
def add_operation_page():
    manufacturer_id = _get_manufacturer_id_web_or_jwt()

    if not manufacturer_id:
        return redirect("/newlogin")

    return render_template(
        "manufacturer/AddOperation.html",
        active_page="operations",
        active_submenu=None,
        operation=None,
    )


# Register operation
@operations_bp.post("/register")
def register_operation_api():
    manufacturer_id = _get_manufacturer_id_web_or_jwt()

    if not manufacturer_id:
        return jsonify(ok=False, error="unauthorized"), 401

    raw = request.get_json(silent=True) if request.is_json else request.form.to_dict()

    try:
        res = OperationService.register_operation_with_blockchain(
            manufacturer_id=manufacturer_id,
            payload=raw,
        )
        return jsonify(res), (200 if res.get("ok") else 400)

    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500