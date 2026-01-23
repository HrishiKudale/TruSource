# backend/routes/farmer/logistics_routes.py

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from backend.services.farmer.logistics_service import FarmerLogisticsService
from backend.mongo import mongo

logistics_bp = Blueprint("farmer_logistics", __name__, url_prefix="/farmer/logistics")


# -----------------------------------------
# LIST ALL SHIPMENTS FOR FARMER
# GET /farmer/logistics/shipments
# -----------------------------------------
@logistics_bp.get("/shipments")
def list_shipments():
    if session.get("role") != "farmer":
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session.get("user_id")
    if not farmer_id:
        return jsonify({"error": "farmer_id required"}), 400

    # ✅ service returns: {"shipments": [...]}
    data = FarmerLogisticsService.get_shipments(farmer_id)
    shipments = data.get("shipments", [])

    # ✅ KPIs (basic)
    active_shipments = sum(1 for s in shipments if (s.get("status") or "").lower() in ("active", "in_transit"))
    requested_shipments = len(shipments)  # total requests
    pending_payments = sum(
        1 for s in shipments
        if ((s.get("payment_details") or [{}])[0].get("payment_terms", "").strip() != "")
        and (s.get("status") or "").lower() in ("pending", "requested")
    )

    return render_template(
        "Logistics.html",
        transporter_request=shipments,   # ✅ IMPORTANT: matches your template
        active_shipments=active_shipments,
        requested_shipments=requested_shipments,
        pending_payments=pending_payments,
        active_page="logistics",
    )


# -----------------------------------------
# SINGLE SHIPMENT DETAILS (JSON)
# GET /farmer/logistics/shipment/<shipment_id>
# -----------------------------------------
@logistics_bp.get("/shipment/<shipment_id>")
def shipment_detail(shipment_id):
    if session.get("role") != "farmer":
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session.get("user_id")
    if not farmer_id:
        return jsonify({"error": "farmer_id required"}), 400

    data = FarmerLogisticsService.get_single_shipment(farmer_id, shipment_id)
    return jsonify(data)


# -----------------------------------------
# ADD SHIPMENT PAGE (GET)
# GET /farmer/logistics/add
# -----------------------------------------
@logistics_bp.get("/add")
def add_shipment_page():
    if session.get("role") != "farmer":
        return redirect(url_for("auth.new_login"))

    farmer_id = session.get("user_id")
    if not farmer_id:
        return jsonify({"error": "farmer_id required"}), 400

    modal_data = FarmerLogisticsService.get_shipment_modal_data(farmer_id)

    shipment_entities = FarmerLogisticsService.get_shipment_entities_from_users()
    transporter_details = FarmerLogisticsService.get_transport_details_from_users()
    vehicles = list(mongo.db.vehicles.find({}))

    return render_template(
        "AddShipment.html",
        orders=modal_data["orders"],
        crops=modal_data["crops"],
        pickup_entities=shipment_entities,
        delivery_entities=shipment_entities,
        transporter_details=transporter_details,
        vehicles=vehicles,
        active_page="logistics",
    )


# -----------------------------------------
# CREATE SHIPMENT REQUEST (POST)
# POST /farmer/logistics/create
# -----------------------------------------
from flask import request, jsonify, redirect, url_for, render_template

@logistics_bp.post("/create")
def create_shipment():
    if session.get("role") != "farmer":
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    farmer_id = session.get("user_id")
    if not farmer_id:
        return jsonify({"ok": False, "error": "farmer_id required"}), 400

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # ----------------------------
    # JSON submit
    # ----------------------------
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        payload["farmer_id"] = farmer_id

        result = FarmerLogisticsService.create_transporter_request(payload)
        if result.get("error"):
            return jsonify({"ok": False, "error": result["error"]}), 400  

        return jsonify({"ok": True, **result}), 201

    # ----------------------------
    # HTML form submit
    # ----------------------------
    form = request.form

    def last_non_empty(name: str) -> str:
        vals = [v for v in form.getlist(name) if (v or "").strip()]
        return vals[-1] if vals else ""

    # --- Shipment Details ---
    shipment_details = [{
        "pickup_from": last_non_empty("pickup_from"),
        "pickup_id": last_non_empty("pickup_id"),
        "pickup_name": form.get("pickup_name", ""),
        "pickup_location": form.get("pickup_location", ""),

        "deliver_to": last_non_empty("deliver_to"),
        "deliver_id": last_non_empty("deliver_id"),
        "deliver_name": form.get("deliver_name", ""),
        "deliver_location": form.get("deliver_location", ""),
    }]

    # --- Transporter Details ---
    transporter_mode = form.get("transporter_mode", "platform")
    transporter_details = [{
        "transporter_mode": transporter_mode,
        "transporter_name": form.get("transporter_name", ""),
        "transporter_id": form.get("transporter_id", ""),
        "personal_transporter_name": form.get("personal_transporter_name", ""),
        "vehicle_type": form.get("vehicle_type", ""),
        "pickup_date": form.get("pickup_date", ""),
        "delivery_date": form.get("delivery_date", ""),
    }]

    # --- Payment Details ---
    insurance_requested = form.get("insurance_requested") in ["on", "true", "1", "yes"]
    payment_details = [{
        "payment_terms": form.get("payment_terms", ""),
        "insurance_requested": insurance_requested,
        "declared_value": form.get("declared_value", ""),
        "coverage_note": form.get("coverage_note", ""),
        "transporter_note": form.get("transporter_note", ""),
    }]

    # --- Shipment Items ---
    items_order_id = form.getlist("items_order_id[]")
    items_order_date = form.getlist("items_order_date[]")
    items_crop_id = form.getlist("items_crop_id[]")
    items_crop_name = form.getlist("items_crop_name[]")
    items_quantity = form.getlist("items_quantity[]")

    max_len = max(
        len(items_order_id),
        len(items_order_date),
        len(items_crop_id),
        len(items_crop_name),
        len(items_quantity),
        0
    )

    shipment_items = []
    for i in range(max_len):
        row = {
            "order_id": items_order_id[i] if i < len(items_order_id) else "",
            "order_date": items_order_date[i] if i < len(items_order_date) else "",
            "crop_id": items_crop_id[i] if i < len(items_crop_id) else "",
            "crop_name": items_crop_name[i] if i < len(items_crop_name) else "",
            "quantity": items_quantity[i] if i < len(items_quantity) else "",
        }

        # ✅ IMPORTANT: skip empty rows
        if not (row["order_id"] or row["crop_id"] or row["crop_name"]) and not str(row["quantity"]).strip():
            continue

        shipment_items.append(row)

    payload = {
        "farmer_id": farmer_id,
        "shipment_details": shipment_details,
        "transporter_details": transporter_details,
        "payment_details": payment_details,
        "shipment_items": shipment_items,
    }

    result = FarmerLogisticsService.create_transporter_request(payload)

    if result.get("error"):
        if is_ajax:
            return jsonify({"ok": False, "error": result["error"]}), 400

        # HTML re-render
        modal_data = FarmerLogisticsService.get_shipment_modal_data(farmer_id)
        shipment_entities = FarmerLogisticsService.get_shipment_entities_from_users()
        transporter_details_dd = FarmerLogisticsService.get_transport_details_from_users()
        vehicles = list(mongo.db.vehicles.find({}))

        return render_template(
            "AddShipment.html",
            error=result["error"],
            orders=modal_data["orders"],
            crops=modal_data["crops"],
            pickup_entities=shipment_entities,
            delivery_entities=shipment_entities,
            transporter_details=transporter_details_dd,
            vehicles=vehicles,
            active_page="logistics",
        ), 400

    # ✅ SUCCESS: return JSON for AJAX so modal can show success state
    if is_ajax:
        return jsonify({"ok": True, **result}), 201

    return redirect(url_for("farmer_logistics.list_shipments"))



@logistics_bp.get("/request/<request_id>")
def shipment_info_page(request_id):
    if session.get("role") != "farmer":
        return redirect(url_for("auth.new_login"))

    farmer_id = session.get("user_id")
    if not farmer_id:
        return jsonify({"error": "farmer_id required"}), 400

    data = FarmerLogisticsService.get_shipment_info_page_data(farmer_id, request_id)
    if data.get("error"):
        return render_template(
            "ShipmentInfo.html",
            error=data["error"],
            active_page="logistics",
        ), 404

    return render_template(
        "ShipmentInfo.html",
        active_page="logistics",
        **data
    )
