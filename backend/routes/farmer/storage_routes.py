# backend/routes/farmer/storage_routes.py

from flask import (
    Blueprint,
    render_template,
    session,
    jsonify,
    redirect,
    request,
)

from backend.services.farmer.processing_service import FarmerProcessingService
from backend.services.farmer.storage_service import FarmerStorageService
from backend.services.farmer.crop_service import CropService
from backend.mongo import mongo

# IMPORTANT: name must match what you use in url_for('farmer_storage.list_storage')
storage_bp = Blueprint(
    "farmer_storage",
    __name__,
    url_prefix="/farmer/storage",
)


# ----------------------------------------------------
# 1) STORAGE OVERVIEW / LIST PAGE
#    GET  /farmer/storage/list
# ----------------------------------------------------
# backend/routes/farmer/storage_routes.py

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

        # ✅ KPIs
        total_warehouses=kpis["total_warehouses"],
        total_capacity=kpis["total_capacity"],
        shipments_linked=kpis["shipments_linked"],
        total_stored=kpis["total_stored"],
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

    # Warehouses: from users collection (role = "warehouse")
    warehouses = list(
        mongo.db.users.find(
            {"role": "warehouse"},
            {
                "_id": 0,
                "userId": 1,          # acts as warehouseId if you don't have a separate field
                "warehouseId": 1,
                "name": 1,
                "location": 1,
            },
        )
    )

    # Crops for this farmer (for crop dropdowns)
    crop_data = CropService.get_my_crops(farmer_id)
    crops = crop_data.get("crops", [])
    return render_template(
        "AddStorage.html",
        active_page="storage",
        active_submenu="warehouse",
        warehouses=warehouses,
        crops=crops,
        items=[],
        error=None,
    )


# ----------------------------------------------------
# 3) SUBMIT STORAGE REQUEST
#    POST /farmer/storage/add
# ----------------------------------------------------
@storage_bp.post("/add")
def submit_storage_request():
    """
    Handles the POST from AddStorage.html.
    Uses FarmerStorageService.create_storage_requests()
    to insert docs into farmer_request with requestKind='storage'.
    """
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect("/newlogin")

    farmer_id = session["user_id"]
    res = FarmerStorageService.create_storage_requests(farmer_id, request.form)

    # If something went wrong, re-render form with error
    if not res.get("ok"):
        # Re-build dropdown data
        warehouses = list(
            mongo.db.users.find(
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
        crops = CropService.get_my_crops(farmer_id)

        return render_template(
            "AddStorage.html",
            active_page="storage",
            active_submenu="warehouse",
            warehouses=warehouses,
            crops=crops,
            error=res.get("error", "Failed to create storage request."),
        ), 400

    # On success, go back to list page
    return redirect("/farmer/storage/list")


# ----------------------------------------------------
# 4) OPTIONAL JSON API
#    GET /farmer/storage/api/list
# ----------------------------------------------------
@storage_bp.get("/api/list")
def storage_list_api():
    if session.get("role") != "farmer" or not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session["user_id"]
    items = FarmerStorageService.list_storage(farmer_id)
    return jsonify({"ok": True, "items": items})




# ==========================================================
# ✅ NEW: Warehouse Info Page (HTML)
# GET /farmer/storage/warehouse/<request_id>
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
# ✅ NEW: Warehouse Info API (JSON)
# GET /farmer/storage/api/warehouse/<request_id>
# ==========================================================
@storage_bp.get("/api/warehouse/<request_id>")
def warehouse_info_api(request_id):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401

    farmer_id = session["user_id"]
    data = FarmerStorageService.get_warehouse_info_page_data(farmer_id, request_id)

    if not data.get("ok"):
        return jsonify(data), 404
    return jsonify(data)
