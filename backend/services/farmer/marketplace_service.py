# backend/services/farmer/marketplace_service.py

from datetime import datetime, timezone

from bson import ObjectId
from backend.mongo import mongo


class MarketService:

    @staticmethod
    def get_active_demand_for_farmer():
        """
        Fetches marketplace demands visible to all farmers.
        Returns rows shaped EXACTLY for Marketplace.html (snake_case keys).
        """
        db = mongo.db.marketplace  # ✅ collection name: marketplace

        now = datetime.now(timezone.utc)

        # Only visible to all farmers
        query = {
            "visibility.scope": "all_farmers",
        }

        docs = list(db.find(query).sort("created_at", -1))

        rows = []
        for d in docs:
            created_at = d.get("created_at")
            expiry_dt  = d.get("expiryDate") or d.get("expiry")  # support both

            # Try to auto-close expired rows (optional)
            is_expired = False
            if isinstance(expiry_dt, datetime):
                is_expired = expiry_dt < now
            elif isinstance(expiry_dt, str):
                # if stored as "YYYY-MM-DD"
                try:
                    expiry_dt_parsed = datetime.fromisoformat(expiry_dt.replace("Z", "+00:00"))
                    is_expired = expiry_dt_parsed < now
                except Exception:
                    pass

            status = d.get("status", "Active")
            if is_expired and status.lower() == "active":
                status = "Expired"

            # Format Posted On
            posted_on = "-"
            if isinstance(created_at, datetime):
                posted_on = created_at.strftime("%d %b %Y")

            # Format Expiry
            expiry = "-"
            if isinstance(expiry_dt, datetime):
                expiry = expiry_dt.strftime("%d %b %Y")
            elif isinstance(expiry_dt, str) and expiry_dt.strip():
                expiry = expiry_dt
            rows.append({
                 "_id": str(d["_id"]), # ✅ IMPORTANT for opening MarketInfo page
                "posted_on": posted_on,
                "buyer": d.get("buyer_name") or d.get("buyerName") or "-",
                "crop_name": d.get("crop_name") or d.get("cropType") or "-",
                "buyer_type": d.get("buyer_type") or d.get("buyerType") or "-",
                "location": d.get("location") or "-",
                "offered_price": d.get("offered_price") or d.get("offeredPrice") or "-",
                "quantity": d.get("quantity") or d.get("marketQuantity") or "-",
                "expiry": expiry,
                "status": status,
            })

        return rows



    @staticmethod
    def get_my_listings(farmer_id: str):
        """
        Returns rows EXACTLY as Marketplace.html expects
        """
        db = mongo.db.marketplace

        docs = list(
            db.find(
                {
                    "type": "listing",
                    "farmer_id": farmer_id
                }
            ).sort("created_at", -1)
        )

        rows = []
        for d in docs:
            # Listing ID
            listing_id = str(d.get("_id"))

            # Crop
            crop_name = d.get("crop_name") or d.get("cropType") or "-"

            # Quantity
            quantity = d.get("quantity") or "-"

            # Price
            price_val = d.get("price_value")
            price_unit = d.get("price_unit", "")

            if price_val is not None:
                offered_price = f"₹{price_val} / {price_unit}"
            else:
                offered_price = d.get("offered_price") or "-"

            # Offer
            negotiable = d.get("negotiable", False)
            offer = "Negotiable" if negotiable else "Fixed"

            # Status
            status = d.get("status", "Active")

            rows.append({
                "listing_id": listing_id,
                "crop_name": crop_name,
                "quantity": quantity,
                "offered_price": offered_price,
                "offer": offer,
                "status": status
            })

        return rows



    @staticmethod
    def create_listing(farmer_id: str, payload: dict):
        db = mongo.db.marketplace

        payload = payload or {}

        crop_id = payload.get("crop_id")
        crop_name = payload.get("crop_name")
        quantity = payload.get("quantity")
        price_value = payload.get("price_value")
        price_unit = payload.get("price_unit")

        if not crop_id or not crop_name:
            return {"error": "crop_id and crop_name are required"}

        try:
            quantity = float(quantity)
        except Exception:
            return {"error": "quantity must be a number"}

        try:
            price_value = float(price_value)
        except Exception:
            return {"error": "price_value must be a number"}

        if quantity <= 0:
            return {"error": "quantity must be > 0"}
        if price_value <= 0:
            return {"error": "price_value must be > 0"}

        now = datetime.now(timezone.utc)

        doc = {
            "type": "listing",

            "farmer_id": farmer_id,
            "farmer_name": payload.get("farmer_name", ""),

            "crop_id": crop_id,
            "crop_name": crop_name,

            "quantity": quantity,
            "minimum_order_quantity": float(payload.get("minimum_order_quantity") or 0),

            "price_value": price_value,
            "price_unit": price_unit or "kg",
            "negotiable": bool(payload.get("negotiable", False)),

            "target_buyer_type": (payload.get("target_buyer_type") or "").lower(),

            "payment_terms": payload.get("payment_terms", ""),
            "delivery": payload.get("delivery", ""),

            "pickup_name": payload.get("pickup_name", ""),
            "pickup_location": payload.get("pickup_location", ""),

            "expiry": payload.get("expiry", ""),
            "status": payload.get("status", "Active"),

            "created_at": now,
            "updated_at": now,
        }

        inserted = db.insert_one(doc)
        return {"success": True, "listing_id": str(inserted.inserted_id)}





    @staticmethod
    def get_demand_info(demand_id: str):
        db_market = mongo.db.marketplace
        db_users = mongo.db.users

        try:
            oid = ObjectId(demand_id)
        except Exception:
            return {"error": "Invalid demand id"}

        demand_doc = db_market.find_one({"_id": oid})
        if not demand_doc:
            return {"error": "Demand not found"}

        # Fetch buyer (try common keys)
        buyer_id = demand_doc.get("buyer_id") or demand_doc.get("buyerId") or demand_doc.get("buyer_id")
        buyer_doc = db_users.find_one({"user_id": buyer_id}) or db_users.find_one({"userId": buyer_id}) or {}

        # Normalize demand for template (snake_case)
        demand = {
            "_id": str(demand_doc.get("_id")),
            "status": demand_doc.get("status", "Active"),
            "created_at": demand_doc.get("created_at") or demand_doc.get("posted_on") or "-",

            "buyer_type": demand_doc.get("buyer_type") or demand_doc.get("buyerType") or "-",
            "buyer_name": demand_doc.get("buyer_name") or demand_doc.get("buyerName") or "-",

            "crop_name": demand_doc.get("crop_name") or demand_doc.get("cropType") or "-",
            "crop_variety": demand_doc.get("crop_variety") or demand_doc.get("cropVariety") or "-",

            "quantity": demand_doc.get("quantity") or demand_doc.get("marketQuantity") or "-",
            "quantity_unit": demand_doc.get("quantity_unit") or demand_doc.get("quantityUnit") or "",

            "offered_price": demand_doc.get("offered_price") or demand_doc.get("offeredPrice") or "-",
            "price_unit": demand_doc.get("price_unit") or demand_doc.get("priceUnit") or "",

            "expiry": demand_doc.get("expiry") or demand_doc.get("expiryDate") or "-",
            "payment_terms": demand_doc.get("payment_terms") or demand_doc.get("paymentTerms") or "-",
            "delivery": demand_doc.get("delivery") or demand_doc.get("deliveryPreference") or "-",
        }

        # negotiable: distinguish between missing and false
        negotiable_val = demand_doc.get("negotiable", None)
        demand["negotiable"] = negotiable_val  # True/False/None

        # Normalize buyer for summary card
        buyer = {
            "name": buyer_doc.get("name") or buyer_doc.get("fullName") or demand["buyer_name"] or "-",
            "office_address": buyer_doc.get("officeAddress") or buyer_doc.get("location") or buyer_doc.get("city") or "-",
            "phone": buyer_doc.get("phone") or buyer_doc.get("mobile") or buyer_doc.get("contact") or "-",
            "email": buyer_doc.get("email") or "-",
        }

        return {"demand": demand, "buyer": buyer}

        # in MarketService (recommended)
    @staticmethod
    def get_pickup_entities_for_market():
        # Example: load warehouse/manufacturer from users collection
        # Adjust query to your schema
        docs = mongo.db.users.find(
            {"role": {"$in": ["warehouse", "manufacturer"]}},
            {"_id": 0, "userId": 1, "name": 1, "location": 1}
        )

        out = []
        for d in docs:
            out.append({
                "entityId": d.get("userId", ""),
                "name": d.get("name", ""),
                "location": d.get("location", "")           
            })
        return out


    @staticmethod
    def submit_negotiation(demand_id: str, farmer_id: str, proposed_price, price_unit: str, note: str):
        db_market = mongo.db.marketplace

        # Validate demand id
        try:
            oid = ObjectId(demand_id)
        except Exception:
                return {"error": "Invalid demand id"}

        demand = db_market.find_one({"_id": oid})
        if not demand:
                return {"error": "Demand not found"}

            # Validate price
        try:
                proposed_price = float(proposed_price)
        except Exception:
                return {"error": "Enter a valid proposed price"}

        if proposed_price <= 0:
                return {"error": "Proposed price must be greater than 0"}

        nego = {
                "farmer_id": farmer_id,
                "proposed_price": proposed_price,
                "price_unit": (price_unit or "kg").strip(),
                "note": (note or "").strip(),
                "status": "sent",
                "created_at": datetime.now(timezone.utc),
            }

            # ✅ single update: push history + set last + update timestamps
        db_market.update_one(
                {"_id": oid},
                {
                    "$push": {"negotiations": nego},
                    "$set": {
                        "last_negotiation": nego,
                        "updated_at": datetime.now(timezone.utc),
                    }
                }
            )

        return {"success": True}
    


    @staticmethod
    def get_listing_details(farmer_id: str, listing_id: str):
        db_listings = mongo.db.marketplace
        db_req = mongo.db.marketplace_requests

        try:
            oid = ObjectId(listing_id)
        except Exception:
            return {"error": "Invalid listing id"}

        listing = db_listings.find_one({"_id": oid, "type": "listing", "farmer_id": farmer_id})
        if not listing:
            return {"error": "Listing not found"}

        # requests linked to this listing
        reqs = list(db_req.find({"listing_id": str(oid), "farmer_id": farmer_id}).sort("created_at", -1))

        # normalize listing for template
        l = {
            "listing_id": str(listing["_id"]),
            "crop_id": listing.get("crop_id","-"),
            "crop_name": listing.get("crop_name","-"),
            "listed_qty": listing.get("quantity","-"),
            "min_qty": listing.get("minimum_order_quantity","-"),
            "price_value": listing.get("price_value"),
            "price_unit": listing.get("price_unit","kg"),
            "negotiable": bool(listing.get("negotiable", False)),
            "duration": listing.get("expiry","-"),
            "pickup_location": listing.get("pickup_location","-"),
            "target_buyer_type": listing.get("target_buyer_type","-"),
            "payment_terms": listing.get("payment_terms","-"),
            "delivery": listing.get("delivery","-"),
            "status": listing.get("status","Active"),
        }

        # normalize requests for template
        out = []
        for r in reqs:
            out.append({
                "req_id": str(r.get("_id")),
                "buyer_name": r.get("buyer_name","-"),
                "buyer_type": r.get("buyer_type","-"),
                "requested_qty": r.get("requested_qty","-"),
                "price_value": r.get("price_value","-"),
                "price_unit": r.get("price_unit","kg"),
                "note": r.get("note",""),
                "status": r.get("status","requested"),
                "updated_at": r.get("updated_at"),
                "negotiations": r.get("negotiations", []),
                "approved_offer": r.get("approved_offer"),
            })

        return {"listing": l, "requests": out}


    @staticmethod
    def accept_request(farmer_id: str, listing_id: str, req_id: str, payload: dict):
        db_req = mongo.db.marketplace_requests

        try:
            rid = ObjectId(req_id)
        except Exception:
            return {"error": "Invalid request id"}

        req = db_req.find_one({"_id": rid, "farmer_id": farmer_id, "listing_id": listing_id})
        if not req:
            return {"error": "Request not found"}

        # accept current offer OR accept custom offer from payload
        price_value = payload.get("price_value", req.get("price_value"))
        price_unit  = payload.get("price_unit", req.get("price_unit","kg"))
        qty         = payload.get("qty", req.get("requested_qty"))

        try:
            price_value = float(price_value)
            qty = float(qty)
        except Exception:
            return {"error": "Invalid price/qty"}

        now = datetime.now(timezone.utc)

        db_req.update_one(
            {"_id": rid},
            {"$set": {
                "status": "approved",
                "approved_offer": {
                    "price_value": price_value,
                    "price_unit": price_unit,
                    "qty": qty,
                    "approved_at": now
                },
                "updated_at": now
            }}
        )
        return {"success": True}


    @staticmethod
    def counter_offer(farmer_id: str, listing_id: str, req_id: str, payload: dict):
        db_req = mongo.db.marketplace_requests

        try:
            rid = ObjectId(req_id)
        except Exception:
            return {"error": "Invalid request id"}

        req = db_req.find_one({"_id": rid, "farmer_id": farmer_id, "listing_id": listing_id})
        if not req:
            return {"error": "Request not found"}

        price_value = payload.get("price_value")
        price_unit  = (payload.get("price_unit") or "kg").strip()
        note = (payload.get("note") or "").strip()

        try:
            price_value = float(price_value)
        except Exception:
            return {"error": "Enter valid counter price"}

        now = datetime.now(timezone.utc)

        nego = {"by": "farmer", "price_value": price_value, "price_unit": price_unit, "note": note, "created_at": now}

        db_req.update_one(
            {"_id": rid},
            {"$push": {"negotiations": nego},
             "$set": {
                 "status": "negotiation",
                 "price_value": price_value,
                 "price_unit": price_unit,
                 "updated_at": now
             }}
        )
        return {"success": True}


    @staticmethod
    def reject_request(farmer_id: str, listing_id: str, req_id: str):
        db_req = mongo.db.marketplace_requests
        try:
            rid = ObjectId(req_id)
        except Exception:
            return {"error": "Invalid request id"}

        now = datetime.now(timezone.utc)
        res = db_req.update_one(
            {"_id": rid, "farmer_id": farmer_id, "listing_id": listing_id},
            {"$set": {"status": "rejected", "updated_at": now}}
        )
        if res.matched_count == 0:
            return {"error": "Request not found"}
        return {"success": True}




    @staticmethod
    def get_listing_details_for_farmer(farmer_id: str, listing_id: str):
        db = mongo.db.marketplace

        try:
            oid = ObjectId(listing_id)
        except Exception:
            return {"error": "Invalid listing id"}

        doc = db.find_one({"_id": oid, "type": "listing", "farmer_id": farmer_id})
        if not doc:
            return {"error": "Listing not found"}

        # Status logic:
        # - approved if accepted_offer exists
        # - requested if offers exist
        # - none if no offers
        accepted_offer = doc.get("accepted_offer")  # should be a dict

        if accepted_offer:
            status = "approved"
        else:
            offers = doc.get("offers", [])
            status = "requested" if offers else "none"

        # normalize listing for template
        listing = {
            "_id": str(doc.get("_id")),
            "code": doc.get("listing_code") or doc.get("code") or doc.get("listingId") or "LST-001",
            "crop_name": doc.get("crop_name") or doc.get("cropType") or "-",
            "quantity": doc.get("quantity") or "-",
            "quantity_unit": doc.get("quantity_unit") or "Kg",
            "price_value": doc.get("price_value"),
            "price_unit": doc.get("price_unit") or "kg",
            "negotiable": bool(doc.get("negotiable", False)),
            "minimum_order_quantity": doc.get("minimum_order_quantity") or 0,
            "payment_terms": doc.get("payment_terms") or "-",
            "delivery": doc.get("delivery") or "-",
            "location": doc.get("pickup_location") or doc.get("pickupLocation") or doc.get("location") or "-",
            "expiry": doc.get("expiry") or doc.get("listing_duration") or "-",
            "target_buyer_label": (doc.get("target_buyer_type") or "-"),
        }

        accepted = None
        if accepted_offer:
            # format datetime
            dt = accepted_offer.get("order_date")
            order_date_label = "-"
            if isinstance(dt, datetime):
                order_date_label = dt.strftime("%d %b %Y, %I:%M %p")

            # total value
            total_value_label = "-"
            try:
                tv = float(accepted_offer.get("total_order_value", 0))
                total_value_label = f"₹{tv:,.0f}"
            except Exception:
                pass

            accepted = {
                "buyer_id": accepted_offer.get("buyer_id") or "",
                "buyer_name": accepted_offer.get("buyer_name") or "-",
                "buyer_type": accepted_offer.get("buyer_type") or "-",
                "proposed_price": accepted_offer.get("proposed_price") or "-",
                "price_unit": accepted_offer.get("price_unit") or "kg",
                "price_label": accepted_offer.get("price_label") or f"₹{accepted_offer.get('proposed_price','-')}/{accepted_offer.get('price_unit','kg')}",
                "total_value_label": accepted_offer.get("total_value_label") or total_value_label,
                "location": accepted_offer.get("location") or "-",
                "quantity_ordered": accepted_offer.get("quantity_ordered") or "-",
                "quantity_unit": accepted_offer.get("quantity_unit") or "kg",
                "quantity_label": accepted_offer.get("quantity_label") or f"{accepted_offer.get('quantity_ordered','-')} {accepted_offer.get('quantity_unit','kg')}",
                "order_id": accepted_offer.get("order_id") or "-",
                "order_date_label": accepted_offer.get("order_date_label") or order_date_label,
                "note": accepted_offer.get("note") or "-",
            }

        return {"ok": True, "status": status, "listing": listing, "accepted": accepted}
