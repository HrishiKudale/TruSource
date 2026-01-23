# backend/routes/farmer/sales_routes.py
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from datetime import datetime
import random

from backend.mongo import mongo
from backend.services.farmer.orders_service import OrderService
from backend.services.farmer.crop_service import CropService  # if you use blockchain crops

sales_bp = Blueprint("farmer_sales_bp", __name__, url_prefix="/farmer/sales")


# -------------------- PAGES --------------------

@sales_bp.get("/orders")
def orders_page():
    if session.get("role") != "farmer":
        return redirect(url_for("auth.new_login"))

    farmer_id = session.get("user_id")
    if not farmer_id:
        return redirect(url_for("auth.new_login"))

    orders = OrderService.list_orders_for_farmer(farmer_id)
    total_active, total_pending, total_delivered, total_revenue = OrderService.get_kpis(farmer_id)

    return render_template(
        "Orders.html",
        orders=orders,
        total_active_orders=total_active,
        total_pending_orders=total_pending,
        total_delivered_orders=total_delivered,
        total_revenue=total_revenue,
        active_page="sales",
        active_submenu="orders"
    )


# ✅ FIX 405: add GET route for create page
@sales_bp.get("/order/create")
def create_order_page():
    if session.get("role") != "farmer":
        return redirect(url_for("auth.new_login"))

    farmer_id = session.get("user_id")
    if not farmer_id:
        return redirect(url_for("auth.new_login"))

    # requestId comes from URL: /farmer/sales/order/create?requestId=XXXX
    request_id = request.args.get("requestId", "").strip()

    # buyers from users collection
    buyers = list(
        mongo.db.users.find(
            {"role": {"$in": ["manufacturer", "retailer"]}},
            {
                "_id": 0,
                "userId": 1,
                "name": 1,
                "officeName": 1,
                "role": 1,
                "location": 1,
                "address": 1,
                "contactPerson": 1,
                "phone": 1,
                "email": 1
            }
        )
    )

    # crops (blockchain-backed crops)
    crop_data = CropService.get_my_crops(farmer_id)
    crops = crop_data.get("crops", [])

    # warehouses if you want (optional) - keep empty if not needed
    # ✅ warehouses
    warehouses = list(
        mongo.db.users.find(
            {},
            {"_id": 0, "warehouseId": 1, "userId": 1, "name": 1}
        )
    )

    # ✅ farms (farmer’s own farms OR farmer profile address)
    # If you store farms in a collection, use it; otherwise load farmer profile
    farms = list(
        mongo.db.users.find(
            {"farmerId": farmer_id},
            {"_id": 0, "farmId": 1, "name": 1}
        )
    )

    return render_template(
        "AddOrder.html",
        buyers=buyers,
        crops=crops,
        warehouses=warehouses,
        active_page="sales",
        active_submenu="orders",
        farms=farms,
        request_id=request_id
    )





# -------------------- APIs --------------------

@sales_bp.get("/api/generate_order_id")
def api_generate_order_id():
    return jsonify({"orderId": OrderService.generate_order_id()})


# ✅ requestId format: REQ-<FARMER_INITIALS>-<YYYYMMDD>-<5digits>
@sales_bp.get("/api/generate_request_id")
def api_generate_request_id():
    farmer_id = session.get("user_id")
    if not farmer_id:
        return jsonify({"error": "unauthorized"}), 401

    user = mongo.db.users.find_one({"userId": farmer_id}, {"_id": 0, "name": 1})
    name = (user or {}).get("name", "") or ""
    initials = "".join([p[0].upper() for p in name.split()[:2]]) or "FRM"

    date_part = datetime.utcnow().strftime("%Y%m%d")
    rand_part = str(random.randint(10000, 99999))

    return jsonify({"requestId": f"REQ-{initials}-{date_part}-{rand_part}"})


# Prefill from farmer_request
@sales_bp.get("/api/request/<request_id>")
def api_request_prefill(request_id):
    data = OrderService.get_farmer_request(request_id)
    if data.get("error"):
        return jsonify(data), 404
    return jsonify(data)


# Buyer details from users collection
@sales_bp.get("/api/buyer/<buyer_id>")
def api_buyer_details(buyer_id):
    buyer_type = request.args.get("buyerType", "").strip().lower()

    q = {"userId": buyer_id}
    if buyer_type in ["manufacturer", "retailer"]:
        q["role"] = buyer_type

    u = mongo.db.users.find_one(q, {"_id": 0})
    if not u:
        return jsonify({"error": "buyer not found"}), 404

    # normalize fields (support multiple schemas)
    address = u.get("address") or u.get("location") or "-"
    contact_person = u.get("contactPerson") or u.get("contact_person") or u.get("name") or "-"
    phone = u.get("phone") or u.get("contact") or "-"
    email = u.get("email") or "-"

    return jsonify({
        "buyerId": u.get("userId", buyer_id),
        "buyerType": u.get("role", buyer_type),
        "name": u.get("name", "-"),
        "officeName": u.get("officeName", ""),
        "address": address,
        "contactPerson": contact_person,
        "phone": phone,
        "email": email
    })


# -------------------- CREATE ORDER --------------------

@sales_bp.post("/order/create")
def create_order():
    if session.get("role") != "farmer":
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session.get("user_id")
    if not farmer_id:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.form.to_dict(flat=True)
    payload["farmerId"] = farmer_id  # enforce

    result = OrderService.create_order(payload)
    if result.get("error"):
        return jsonify(result), 400

    return jsonify(result), 201


@sales_bp.get("/order/<order_id>")
def orders_info_page(order_id: str):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]

    order = OrderService.get_order_for_farmer(farmer_id, order_id)
    if not order:
        return render_template(
            "OrderInfo.html",
            active_page="sales",
            active_submenu="orders",
            order=None,
            error="Order not found.",
        ), 404

    return render_template(
        "OrderInfo.html",
        active_page="sales",
        active_submenu="orders",
        order=order,
    )

