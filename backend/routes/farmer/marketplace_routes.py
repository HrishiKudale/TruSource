# backend/routes/farmer/marketplace_routes.py

from flask import Blueprint, redirect, render_template, request, session, jsonify, url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

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
    """Web session auth only."""
    if session.get("role") != "farmer":
        return False, redirect(url_for("auth.new_login")), None

    farmer_id = session.get("user_id")
    if not farmer_id:
        return False, redirect(url_for("auth.new_login")), None

    return True, None, farmer_id


def _get_farmer_id_web_or_jwt():
    # 1) Web session auth
    if session.get("role") == "farmer" and session.get("user_id"):
        return session.get("user_id")

    # 2) JWT auth mobile/API
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


def _load_add_marketplace_context(farmer_id: str):
    crop_data = CropService.get_my_crops(farmer_id) or {}
    crops = crop_data.get("crops", []) or []

    return {
        "crops": crops,
    }


# ------------------------------------------------------------
# Web Pages
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
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return resp

    ctx = _load_add_marketplace_context(farmer_id)
    pickup_entities = MarketService.get_pickup_entities_for_market()
    crop = MarketService.get_listing_by_crop(farmer_id, crop_id)

    coord_doc = mongo.db.marketplace.find_one(
        {"farmerId": farmer_id, "cropId": crop_id},
        {"_id": 0, "coordinates": 1},
    )
    coords = coord_doc.get("coordinates", []) if coord_doc else []

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


@marketplace_bp.post("/create")
def create_marketplace_listing():
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return jsonify({"error": "unauthorized"}), 401

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

        return jsonify(result), 400

    if request.is_json:
        return jsonify(result), 201

    return redirect(url_for("farmer_marketplace_bp.marketplace_home"))


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

    result = MarketService.submit_negotiation(
        demand_id=demand_id,
        farmer_id=farmer_id,
        proposed_price=request.form.get("proposed_price"),
        price_unit=request.form.get("price_unit"),
        note=request.form.get("note"),
    )

    if result.get("error"):
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
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return resp

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
        listing=data.get("listing"),
        requests=data.get("requests", []),
        active_page="sales",
        active_submenu="marketplace",
    )


@marketplace_bp.post("/listing/<listing_id>/request/<req_id>/accept")
def accept_buyer_request(listing_id, req_id):
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    result = MarketService.accept_request(farmer_id, listing_id, req_id, payload)

    if result.get("error"):
        return jsonify(result), 400

    return jsonify(result), 200


@marketplace_bp.post("/listing/<listing_id>/request/<req_id>/counter")
def counter_offer(listing_id, req_id):
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    result = MarketService.counter_offer(farmer_id, listing_id, req_id, payload)

    if result.get("error"):
        return jsonify(result), 400

    return jsonify(result), 200


@marketplace_bp.post("/listing/<listing_id>/request/<req_id>/reject")
def reject_request(listing_id, req_id):
    ok, resp, farmer_id = _require_farmer()
    if not ok:
        return jsonify({"error": "unauthorized"}), 401

    result = MarketService.reject_request(farmer_id, listing_id, req_id)

    if result.get("error"):
        return jsonify(result), 400

    return jsonify(result), 200


# ------------------------------------------------------------
# API Routes
# ------------------------------------------------------------

@marketplace_bp.get("/api/home")
def marketplace_home_api():
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    return jsonify({
        "ok": True,
        "active_demand": MarketService.get_active_demand_for_farmer(),
        "listings": MarketService.get_my_listings(farmer_id),
        "top_buyers": [],
    }), 200


@marketplace_bp.get("/api/list")
def marketplace_list_api():
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    listings = MarketService.get_my_listings(farmer_id)

    return jsonify({
        "ok": True,
        "items": listings,
        "listings": listings,
    }), 200


@marketplace_bp.get("/api/crop/add")
def add_market_blank_api():
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    ctx = _load_add_marketplace_context(farmer_id)
    pickup_entities = MarketService.get_pickup_entities_for_market()

    return jsonify({
        "ok": True,
        "crop": None,
        "pickup_entities": pickup_entities,
        "coords": [],
        **ctx,
    }), 200


@marketplace_bp.get("/api/add/<crop_id>")
def add_market_list_api(crop_id: str):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    ctx = _load_add_marketplace_context(farmer_id)
    pickup_entities = MarketService.get_pickup_entities_for_market()
    crop = MarketService.get_listing_by_crop(farmer_id, crop_id)

    coord_doc = mongo.db.marketplace.find_one(
        {"farmerId": farmer_id, "cropId": crop_id},
        {"_id": 0, "coordinates": 1},
    )
    coords = coord_doc.get("coordinates", []) if coord_doc else []

    if not crop:
        crop = {"crop_id": crop_id, "cropId": crop_id}

    return jsonify({
        "ok": True,
        "crop": crop,
        "pickup_entities": pickup_entities,
        "coords": coords,
        **ctx,
    }), 200


@marketplace_bp.post("/api/create")
def create_marketplace_listing_api():
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    payload = request.get_json(silent=True) or {}
    result = MarketService.create_listing(farmer_id, payload)

    if result.get("error"):
        return jsonify(ok=False, err=result["error"], result=result), 400

    return jsonify(ok=True, result=result), 201


@marketplace_bp.get("/api/demand/<demand_id>")
def market_info_api(demand_id):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    data = MarketService.get_demand_info(demand_id)

    if data.get("error"):
        return jsonify(ok=False, err=data["error"]), 404

    return jsonify({
        "ok": True,
        "demand": data.get("demand"),
        "buyer": data.get("buyer"),
    }), 200


@marketplace_bp.post("/api/demand/<demand_id>/negotiate")
def submit_negotiation_api(demand_id):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    payload = request.get_json(silent=True) or {}

    result = MarketService.submit_negotiation(
        demand_id=demand_id,
        farmer_id=farmer_id,
        proposed_price=payload.get("proposed_price"),
        price_unit=payload.get("price_unit"),
        note=payload.get("note"),
    )

    if result.get("error"):
        return jsonify(ok=False, err=result["error"], result=result), 400

    return jsonify(ok=True, result=result), 200


@marketplace_bp.get("/api/listing/<listing_id>")
def listing_details_api(listing_id):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    data = MarketService.get_listing_details(farmer_id, listing_id)

    if data.get("error"):
        return jsonify(ok=False, err=data["error"]), 404

    return jsonify({
        "ok": True,
        "listing": data.get("listing"),
        "requests": data.get("requests", []),
    }), 200


@marketplace_bp.get("/api/listing/<listing_id>/farmer")
def listing_details_for_farmer_api(listing_id):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    data = MarketService.get_listing_details_for_farmer(farmer_id, listing_id)

    if data.get("error"):
        return jsonify(ok=False, err=data["error"]), 404

    return jsonify({
        "ok": True,
        "status": data.get("status"),
        "listing": data.get("listing"),
        "accepted": data.get("accepted"),
    }), 200


@marketplace_bp.post("/api/listing/<listing_id>/request/<req_id>/accept")
def accept_buyer_request_api(listing_id, req_id):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    payload = request.get_json(silent=True) or {}
    result = MarketService.accept_request(farmer_id, listing_id, req_id, payload)

    if result.get("error"):
        return jsonify(ok=False, err=result["error"], result=result), 400

    return jsonify(ok=True, result=result), 200


@marketplace_bp.post("/api/listing/<listing_id>/request/<req_id>/counter")
def counter_offer_api(listing_id, req_id):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    payload = request.get_json(silent=True) or {}
    result = MarketService.counter_offer(farmer_id, listing_id, req_id, payload)

    if result.get("error"):
        return jsonify(ok=False, err=result["error"], result=result), 400

    return jsonify(ok=True, result=result), 200


@marketplace_bp.post("/api/listing/<listing_id>/request/<req_id>/reject")
def reject_request_api(listing_id, req_id):
    farmer_id = _get_farmer_id_web_or_jwt()
    if not farmer_id:
        return jsonify(ok=False, err="auth"), 401

    result = MarketService.reject_request(farmer_id, listing_id, req_id)

    if result.get("error"):
        return jsonify(ok=False, err=result["error"], result=result), 400

    return jsonify(ok=True, result=result), 200