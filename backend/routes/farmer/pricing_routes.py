# backend/routes/farmer/pricing_routes.py
import csv
from io import StringIO
from flask import Blueprint, render_template, session, redirect, jsonify, Response

from backend.services.farmer.pricing_service import FarmerPricingService

pricing_bp = Blueprint("farmer_pricing", __name__, url_prefix="/farmer/pricing")


@pricing_bp.get("/")
def pricing_page():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    pricing_data, filters = FarmerPricingService.get_pricing_tables()

    return render_template(
        "Pricing.html",
        active_page="pricing",
        pricing_data=pricing_data,
        filters=filters
    )


@pricing_bp.get("/info/<kind>/<buyer_id>")
def pricing_info(kind, buyer_id):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    out = FarmerPricingService.get_buyer_info(kind, buyer_id)
    code = 200 if out.get("ok") else 404
    return jsonify(out), code


@pricing_bp.get("/export")
def pricing_export():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    pricing_data, _ = FarmerPricingService.get_pricing_tables()

    # Flatten export
    rows = []
    for r in pricing_data.get("warehouse", []):
        rows.append({"type": "warehouse", **r})
    for r in pricing_data.get("manufacturer", []):
        rows.append({"type": "manufacturer", **r})
    for r in pricing_data.get("transporter", []):
        rows.append({"type": "transporter", **r})

    si = StringIO()
    writer = csv.DictWriter(si, fieldnames=sorted({k for row in rows for k in row.keys()}))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=pricing_export.csv"}
    )
