# backend/routes/farmer/marketplace_routes.py

from flask import Blueprint, redirect, render_template, request, session, jsonify, url_for
from backend.services.farmer.crop_service import CropService
from backend.services.farmer.marketplace_service import MarketService
from backend.mongo import mongo

marketplace_bp = Blueprint(
    "farmer_marketplace_bp",
    __name__,
    url_prefix="/farmer/marketplace",
)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _require_farmer():
    """Returns (ok, response_or_none, farmer_id_or_none)"""
    if session.get("role") != "farmer":
        return False, redirect(url_for("auth.new_login")), None
    farmer_id = session.get("user_id")
    if not farmer_id:
        return False, redirect(url_for("auth.new_login")), None
    return True, None, farmer_id


def _get_pickup_entities_for_dropdown():
    """
    Pickup From dropdown users list.
    Adjust roles below depending on your app's logic.
    This returns [{name, entityId/_id, location}] objects
    that match what your searchable dropdown expects.
    """
    users = mongo.db.users.find(
        {
            "role": {"$in": ["warehouse", "manufacturer", "transporter", "buyer", "fpo", "company"]},
            "name": {"$exists": True, "$ne": ""},
        },
        {"_id": 1, "name": 1, "entityId": 1, "location": 1}
    )

    out = []
    for u in users:
        out.append({
            "name": u.get("name", ""),
            "entityId": u.get("entityId") or str(u.get("_id")),
            "_id": str(u.get("_id")),
            "location": u.get("location", "") or "",
        })

    # Also allow farmer himself as pickup (optional, if needed)
    # farmer_id = session.get("user_id")
    # if farmer_id:
    #     f = mongo.db.users.find_one({"_id": farmer_id}, {"name": 1, "location": 1})
    #     if f:
    #         out.insert(0, {"name": f.get("name","Me"), "entityId": str(farmer_id), "_id": str(farmer_id), "location": f.get("location","")})

    return out


def _load_add_marketplace_context(farmer_id: str):
    crop_data = CropService.get_my_crops(farmer_id) or {}
    crops = crop_data.get("crops", []) or []

    return {
        "crops": crops,
    }



# ------------------------------------------------------------
# Pages
# ------------------------------------------------------------
@marketplace_bp.get("/")
def marketplace_home():
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return resp

    active_demand = MarketService.get_active_demand_for_farmer()
    listings = MarketService.get_my_listings(farmer_id)

    return render_template(
        "Marketplace.html",
        active_demand=active_demand,
        listings=listings,
        top_buyers=[],
        active_page="sales",
        active_submenu="marketplace",
    )


@marketplace_bp.get("/crop/add")
def add_market_blank():
    """Show Add Marketplace form (blank)."""
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return resp
    

    ctx = _load_add_marketplace_context(farmer_id)
    pickup_entities = MarketService.get_pickup_entities_for_market()
    return render_template(
        "AddMarketplace.html",
        active_page="sales",
        active_submenu="marketplace",
        crop=None,
        pickup_entities=pickup_entities,
        coords=[],
        **ctx,
    )


@marketplace_bp.get("/add/<crop_id>")
def add_market_list(crop_id: str):
    """Prefill AddMarketplace.html for selected crop (if marketplace listing exists)."""
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return resp

    ctx = _load_add_marketplace_context(farmer_id)
    pickup_entities = MarketService.get_pickup_entities_for_market()
    crop = MarketService.get_listing_by_crop(farmer_id, crop_id)

    # optional: coordinates if stored in marketplace doc
    coord_doc = mongo.db.marketplace.find_one(
        {"farmerId": farmer_id, "cropId": crop_id},
        {"_id": 0, "coordinates": 1}
    )
    coords = coord_doc.get("coordinates", []) if coord_doc else []

    # If listing doesn't exist, still prefill cropId from crops list (optional)
    if not crop:
        crop = {"crop_id": crop_id, "cropId": crop_id}

    return render_template(
        "AddMarketplace.html",
        active_page="sales",
        active_submenu="marketplace",
        pickup_entities=pickup_entities,
        crop=crop,
        coords=coords,
        **ctx,
    )


# ------------------------------------------------------------
# Create Listing
# ------------------------------------------------------------
@marketplace_bp.post("/create")
def create_marketplace_listing():
    """Create a marketplace listing from AddMarketplace form or JSON."""
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return jsonify({"error": "unauthorized"}), 401

    # IMPORTANT: For HTML form, keep flat=True (your form has single values)
    payload = request.get_json(silent=True) if request.is_json else request.form.to_dict(flat=True)
    payload = payload or {}

    result = MarketService.create_listing(farmer_id, payload)

    if result.get("error"):
        if not request.is_json:
            crop_data = CropService.get_my_crops(farmer_id)
            crops = crop_data.get("crops", [])
            pickup_entities = MarketService.get_pickup_entities_for_market()

            return render_template(
                "AddMarketplace.html",
                active_page="sales",
                active_submenu="marketplace",
                error=result["error"],
                crop=payload,
                crops=crops,
                pickup_entities=pickup_entities,
                coords=[],
            ), 400


    if request.is_json:
        return jsonify(result), 201

    # FIX: redirect to correct endpoint
    return redirect(url_for("farmer_marketplace_bp.marketplace_home"))


# ------------------------------------------------------------
# Demand Pages
# ------------------------------------------------------------
@marketplace_bp.get("/demand/<demand_id>")
def market_info_page(demand_id):
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return resp

    data = MarketService.get_demand_info(demand_id)

    if data.get("error"):
        return render_template(
            "MarketInfo.html",
            error=data["error"],
            active_page="sales",
            active_submenu="marketplace",
        ), 404

    return render_template(
        "MarketInfo.html",
        demand=data.get("demand"),
        buyer=data.get("buyer"),
        active_page="sales",
        active_submenu="marketplace",
    )


@marketplace_bp.post("/demand/<demand_id>/negotiate")
def submit_negotiation(demand_id):
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return resp

    proposed_price = request.form.get("proposed_price")
    price_unit = request.form.get("price_unit")
    note = request.form.get("note")

    result = MarketService.submit_negotiation(
        demand_id=demand_id,
        farmer_id=farmer_id,
        proposed_price=proposed_price,
        price_unit=price_unit,
        note=note,
    )

    if result.get("error"):
        # Make sure demand data is proper
        data = MarketService.get_demand_info(demand_id)
        return render_template(
            "MarketInfo.html",
            demand=data.get("demand"),
            buyer=data.get("buyer"),
            error=result["error"],
            active_page="sales",
            active_submenu="marketplace",
        ), 400

    return redirect(url_for("farmer_marketplace_bp.market_info_page", demand_id=demand_id))


@marketplace_bp.get("/listing/<listing_id>")
def listing_details_page(listing_id):
    if session.get("role") != "farmer":
        return redirect(url_for("auth.new_login"))

    farmer_id = session.get("user_id")
    if not farmer_id:
        return redirect(url_for("auth.new_login"))

    data = MarketService.get_listing_details(farmer_id, listing_id)
    if data.get("error"):
        return render_template(
            "ListingInfo.html",
            error=data["error"],
            listing=None,
            requests=[],
            active_page="sales",
            active_submenu="marketplace",
        ), 404

    return render_template(
        "ListingInfo.html",
        listing=data["listing"],
        requests=data["requests"],
        active_page="sales",
        active_submenu="marketplace",
    )
@marketplace_bp.post("/listing/<listing_id>/request/<req_id>/accept")
def accept_buyer_request(listing_id, req_id):
    if session.get("role") != "farmer":
        return jsonify({"error":"unauthorized"}), 401
    farmer_id = session.get("user_id")

    payload = request.get_json(silent=True) or {}
    result = MarketService.accept_request(farmer_id, listing_id, req_id, payload)

    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result), 200


@marketplace_bp.post("/listing/<listing_id>/request/<req_id>/counter")
def counter_offer(listing_id, req_id):
    if session.get("role") != "farmer":
        return jsonify({"error":"unauthorized"}), 401
    farmer_id = session.get("user_id")

    payload = request.get_json(silent=True) or {}
    result = MarketService.counter_offer(farmer_id, listing_id, req_id, payload)

    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result), 200


@marketplace_bp.post("/listing/<listing_id>/request/<req_id>/reject")
def reject_request(listing_id, req_id):
    if session.get("role") != "farmer":
        return jsonify({"error":"unauthorized"}), 401
    farmer_id = session.get("user_id")

    result = MarketService.reject_request(farmer_id, listing_id, req_id)
    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result), 200



@marketplace_bp.get("/listing/<listing_id>")
def listing_details(listing_id):
    if session.get("role") != "farmer" or not session.get("user_id"):
        return redirect(url_for("auth.new_login"))

    farmer_id = session["user_id"]

    data = MarketService.get_listing_details_for_farmer(farmer_id, listing_id)
    if data.get("error"):
        return render_template(
            "Marketplace.html",
            active_page="sales",
            active_submenu="marketplace",
            active_demand=MarketService.get_active_demand_for_farmer(),
            listings=MarketService.get_my_listings(farmer_id),
            top_buyers=[],
            error=data["error"]
        ), 404

    return render_template(
        "ListingInfo.html",
        active_page="sales",
        active_submenu="marketplace",
        status=data["status"],
        listing=data["listing"],
        accepted=data.get("accepted"),
    )
