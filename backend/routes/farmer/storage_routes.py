# backend/routes/farmer/storage_routes.py

from flask import (
    Blueprint,
    render_template,
    session,
    jsonify,
    redirect,
    request,
)
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from backend.mongo_safe import get_col
from backend.services.farmer.storage_service import FarmerStorageService
from backend.services.farmer.crop_service import CropService

storage_bp = Blueprint(
    "farmer_storage",
    __name__,
    url_prefix="/farmer/storage",
)

def _get_farmer_id_web_or_jwt():
    # 1) Web session auth
    if session.get("role") == "farmer" and session.get("user_id"):
        return session.get("user_id")

    # 2) JWT auth (mobile)
    try:
        verify_jwt_in_request(optional=True)

        user_id = get_jwt_identity()   # ✅ string now
        claims = get_jwt() or {}
        role = (claims.get("role") or "").lower()

        if role == "farmer" and user_id:
            return user_id
        return None
    except Exception:
        return None


# ----------------------------------------------------
# 1) STORAGE OVERVIEW / LIST PAGE
#    GET  /farmer/storage/list
# ----------------------------------------------------
@storage_bp.get("/list")
def list_storage():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]

    storage_items = FarmerStorageService.list_storage(farmer_id)
    kpis = FarmerStorageService.get_kpis(farmer_id)

    return render_template(
        "Warehouses.html",
        active_page="storage",
        active_submenu="warehouse",
        storage_items=storage_items,
        total_warehouses=kpis.get("total_warehouses", 0),
        total_capacity=kpis.get("total_capacity", 0),
        shipments_linked=kpis.get("shipments_linked", 0),
        total_stored=kpis.get("total_stored", 0),
    )


# ----------------------------------------------------
# 2) ADD STORAGE PAGE (FORM)
#    GET  /farmer/storage/add
# ----------------------------------------------------
@storage_bp.get("/add")
def add_storage_page():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]

    # Warehouses dropdown (Mongo)
    users_col = get_col("users")
    warehouses = []
    mongo_error = None

    if users_col is not None:
        warehouses = list(
            users_col.find(
                {"role": "warehouse"},
                {
                    "_id": 0,
                    "userId": 1,
                    "warehouseId": 1,
                    "name": 1,
                    "location": 1,
                    "storage_services.rate_per_kg_day": 1,  # add rate
                },
            )
        )
    else:
        mongo_error = "Mongo is disabled/unavailable. Warehouse list cannot be loaded."

    # Crops dropdown (Blockchain-based)
    crop_data = CropService.get_my_crops(farmer_id)
    crops = crop_data.get("crops", [])

    return render_template(
        "AddStorage.html",
        active_page="storage",
        active_submenu="warehouse",
        coord_doc=warehouses,   # template variable name unchanged
        warehouses=warehouses,
        crops=crops,
        items=[],
        error=mongo_error,
    )


# ----------------------------------------------------
# 3) SUBMIT STORAGE REQUEST
#    POST /farmer/storage/add
# ----------------------------------------------------
@storage_bp.post("/add")
def submit_storage_request():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    res = FarmerStorageService.create_storage_requests(farmer_id, request.form)

    if not res.get("ok"):
        users_col = get_col("users")
        warehouses = []
        if users_col is not None:
            warehouses = list(
                users_col.find(
                    {"role": "warehouse"},
                    {
                        "_id": 0,
                        "userId": 1,
                        "warehouseId": 1,
                        "name": 1,
                        "location": 1,
                    },
                )
            )

        crop_data = CropService.get_my_crops(farmer_id)
        crops = crop_data.get("crops", [])

        return render_template(
            "AddStorage.html",
            active_page="storage",
            active_submenu="warehouse",
            coord_doc=warehouses,
            warehouses=warehouses,   # ✅ ADD THIS LINE
            crops=crops,
            items=[],
            error=res.get("error", "Failed to create storage request."),
        ), 400

    return redirect("/farmer/storage/list")


# ----------------------------------------------------
# 4) OPTIONAL JSON API
#    GET /farmer/storage/api/list
# ----------------------------------------------------
@storage_bp.get("/api/list")
def storage_list_api():
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    farmer_id = session["user_id"]
    items = FarmerStorageService.list_storage(farmer_id)
    return jsonify({"ok": True, "items": items})


# ==========================================================
# Warehouse Info Page (HTML)
# GET /farmer/storage/warehouse/<warehouse_id>
# ==========================================================
@storage_bp.get("/warehouse/<warehouse_id>")
def warehouse_info_page(warehouse_id):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    data = FarmerStorageService.get_warehouse_info_page_data(farmer_id, warehouse_id)

    if not data.get("ok"):
        return render_template(
            "WarehouseInfo.html",
            active_page="storage",
            active_submenu="warehouse",
            error=data.get("error"),
            warehouse=None,
            crops=[],
            warehouse_id=warehouse_id
        ), 404

    return render_template(
        "WarehouseInfo.html",
        active_page="storage",
        active_submenu="warehouse",
        error=None,
        warehouse=data["warehouse"],
        crops=data["crops"],
        warehouse_id=data["warehouse_id"],
    )


# ==========================================================
# Warehouse Info API (JSON)
# GET /farmer/storage/api/warehouse/<warehouse_id>
# ==========================================================
@storage_bp.get("/api/warehouse/<warehouse_id>")
def warehouse_info_api(warehouse_id):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    farmer_id = session["user_id"]
    data = FarmerStorageService.get_warehouse_info_page_data(farmer_id, warehouse_id)

    if not data.get("ok"):
        return jsonify(data), 404
    return jsonify(data)


@storage_bp.get("/api/add")
def submit_storage_request_api():
    # -----------------------------
    # 1. AUTH CHECK
    # -----------------------------
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    # -----------------------------
    # 2. PROCESS STORAGE REQUEST
    # -----------------------------
    data = request.get_json(silent=True) or request.form
    res = FarmerStorageService.create_storage_requests(farmer_id, data)

    # -----------------------------
    # 3. FAILURE → RETURN ERROR JSON
    # -----------------------------
    if not res.get("ok"):
        return jsonify({
            "ok": False,
            "err": res.get("error", "Failed to create storage request.")
        }), 400

    # -----------------------------
    # 4. SUCCESS → RETURN SUCCESS JSON
    # -----------------------------
    return jsonify({
        "ok": True,
        "msg": "Storage request created successfully",
        "storage": res.get("storage", {})   # optional payload
    })