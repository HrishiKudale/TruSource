# backend/services/farmer/pricing_service.py
from typing import Any, Dict, List, Tuple
from backend.mongo import mongo


def _summary(items: List[str], max_first: int = 1) -> str:
    items = [x for x in (items or []) if x and str(x).strip()]
    if not items:
        return "-"
    first = items[0]
    extra = len(items) - 1
    return f"{first}...+{extra}" if extra > 0 else first


class FarmerPricingService:
    """
    Reads buyer pricing from users collection.
    This is flexible: if your schema differs, just map fields inside these builders.
    """

    @staticmethod
    def _get_users_with_services() -> List[Dict[str, Any]]:
        # You can refine filters later (roles, flags, etc.)
        return list(mongo.db.users.find({}))

    @staticmethod
    def get_pricing_tables() -> Tuple[Dict[str, Any], Dict[str, Any]]:
        users = FarmerPricingService._get_users_with_services()

        warehouse_rows: List[Dict[str, Any]] = []
        manufacturer_rows: List[Dict[str, Any]] = []
        transporter_rows: List[Dict[str, Any]] = []

        processing_types_set = set()

        for u in users:
            buyer_id = u.get("userId") or u.get("entityId") or u.get("_id")
            buyer_id = str(buyer_id) if buyer_id else ""
            name = u.get("officeName") or u.get("name") or "-"
            location = u.get("location") or "-"

            # --------- WAREHOUSE ----------
            # expected: u.storage_services = [{storage_type, storage_capacity, storage_temprature, rate_per_kg_day,...}]
            ss = u.get("storage_services")
            if isinstance(ss, list) and ss:
                ss0 = ss[0] or {}
                storage_type = ss0.get("storage_type") or ss0.get("type") or "Cold Storage"
                # rate label for table (simple)
                rate = ss0.get("rate") or ss0.get("rate_per_kg_day") or ss0.get("price") or ""
                rate_label = f"₹{rate} /kg/day" if rate and "₹" not in str(rate) else (str(rate) if rate else "-")

                warehouse_rows.append({
                    "kind": "warehouse",
                    "buyerId": buyer_id,
                    "name": name,
                    "location": location,
                    "storageType": storage_type,
                    "rateLabel": rate_label,
                })

            # --------- MANUFACTURER ----------
            # expected: u.processing_services = [{crop, processing_type, rate, tat}]
            ps = u.get("processing_services") or u.get("manufacturer_services")
            if isinstance(ps, list) and ps:
                crops = []
                proc_types = []
                rates = []
                tats = []

                for x in ps:
                    crop = x.get("crop") or x.get("crop_name") or x.get("cropType")
                    pt = x.get("processing_type") or x.get("processingType")
                    rate = x.get("rate") or x.get("price") or x.get("rate_per_kg")
                    tat = x.get("tat") or x.get("turnaround_time") or x.get("turnaround")

                    if crop: crops.append(str(crop))
                    if pt:
                        proc_types.append(str(pt))
                        processing_types_set.add(str(pt))
                    if rate: rates.append(str(rate))
                    if tat: tats.append(str(tat))

                manufacturer_rows.append({
                    "kind": "manufacturer",
                    "buyerId": buyer_id,
                    "name": name,
                    "location": location,
                    "cropSummary": _summary(crops),
                    "processingSummary": _summary(proc_types),
                    "rateSummary": _summary([f"₹{r}" if "₹" not in r else r for r in rates]),
                    "tatSummary": _summary(tats),
                })

            # --------- TRANSPORTER ----------
            # expected: u.transport_services = [{vehicle_type, base_charge, per_km_rate, loading_unloading, ...}]
            ts = u.get("transport_services") or u.get("transporter_services")
            if isinstance(ts, list) and ts:
                # some high-level fields (first service or from profile)
                coverage = u.get("coverage") or "Within District, Inter-District, Long Distance"
                tracking = u.get("tracking") or "Live GPS Tracking"

                transporter_rows.append({
                    "kind": "transporter",
                    "buyerId": buyer_id,
                    "name": name,
                    "location": location,
                    "coverage": coverage,
                    "tracking": tracking,
                })

        pricing_data = {
            "warehouse": warehouse_rows,
            "manufacturer": manufacturer_rows,
            "transporter": transporter_rows,
        }

        filters = {
            "processing_types": sorted(list(processing_types_set))
        }

        return pricing_data, filters

    @staticmethod
    def get_buyer_info(kind: str, buyer_id: str) -> Dict[str, Any]:
        u = mongo.db.users.find_one({"userId": buyer_id}) or mongo.db.users.find_one({"entityId": buyer_id})
        if not u:
            return {"ok": False, "error": "Buyer not found"}

        name = u.get("officeName") or u.get("name") or "-"
        location = u.get("location") or "-"
        description = u.get("description") or "—"
        phone = u.get("phone") or "-"
        contact_person = u.get("contactPerson") or u.get("name") or "-"
        year = u.get("establishmentYear") or u.get("year") or "-"
        gst = u.get("gstNumber") or u.get("gst") or "-"

        # images (optional)
        image = u.get("image") or u.get("coverImage") or ""
        thumbs = u.get("images") if isinstance(u.get("images"), list) else []

        # ---- Warehouse modal ----
        if kind == "warehouse":
            ss = u.get("storage_services") or []
            ss0 = (ss[0] or {}) if isinstance(ss, list) and ss else {}

            # options table (storage type + rate)
            table_rows = []
            for x in (ss if isinstance(ss, list) else []):
                st = x.get("storage_type") or x.get("type") or "-"
                rate = x.get("rate") or x.get("rate_per_kg_day") or x.get("price") or "-"
                rate_txt = f"₹{rate} /kg/day" if rate != "-" and "₹" not in str(rate) else str(rate)
                table_rows.append({"storageType": st, "rate": rate_txt})

            storage_options = []
            # show common options like screenshot (Cold Storage / Dry Storage)
            for x in (ss if isinstance(ss, list) else []):
                st = x.get("storage_type") or x.get("type")
                rate = x.get("rate") or x.get("rate_per_kg_day") or x.get("price")
                if st and rate:
                    storage_options.append({"label": st, "value": f"₹{rate} /kg/day" if "₹" not in str(rate) else str(rate)})

            data = {
                "name": name,
                "location": location,
                "description": description,
                "phone": phone,
                "contactPerson": contact_person,
                "establishmentYear": year,
                "gstNumber": gst,
                "image": image,
                "thumbs": thumbs,

                "temperatureRange": ss0.get("temperature_range") or ss0.get("storage_temprature") or "0°C – 25°C",
                "humidityControl": ss0.get("humidity_control") or "Available",
                "transportSupport": ss0.get("transport_support") or "Available",
                "storageCapacity": ss0.get("storage_capacity") or "Up to -",

                "storageOptions": storage_options,
                "tableRows": table_rows,
            }
            return {"ok": True, "data": data}

        # ---- Manufacturer modal ----
        if kind == "manufacturer":
            ps = u.get("processing_services") or u.get("manufacturer_services") or []
            table_rows = []
            for x in (ps if isinstance(ps, list) else []):
                table_rows.append({
                    "crop": x.get("crop") or x.get("crop_name") or x.get("cropType") or "-",
                    "processingType": x.get("processing_type") or x.get("processingType") or "-",
                    "rate": (f"₹{x.get('rate')}/kg" if x.get("rate") else (x.get("rate_per_kg") or x.get("price") or "-")),
                    "tat": x.get("tat") or x.get("turnaround_time") or x.get("turnaround") or "-",
                })

            data = {
                "name": name,
                "location": location,
                "description": description,
                "phone": phone,
                "contactPerson": contact_person,
                "establishmentYear": year,
                "gstNumber": gst,
                "image": image,
                "thumbs": thumbs,

                "servicesLabel": u.get("servicesLabel") or "Processing, Packaging",
                "qualityLabel": u.get("qualityLabel") or "High standards",
                "facilityLabel": u.get("facilityLabel") or "24/7 monitored",

                "tableRows": table_rows,
            }
            return {"ok": True, "data": data}

        # ---- Transporter modal ----
        if kind == "transporter":
            ts = u.get("transport_services") or u.get("transporter_services") or []
            table_rows = []
            for x in (ts if isinstance(ts, list) else []):
                table_rows.append({
                    "vehicleType": x.get("vehicle_type") or x.get("type") or "-",
                    "baseCharge": x.get("base_charge") or x.get("base") or "-",
                    "perKmRate": x.get("per_km_rate") or x.get("perKm") or "-",
                    "loading": x.get("loading_unloading") or x.get("loading") or "-",
                })

            data = {
                "name": name,
                "location": location,
                "description": description,
                "phone": phone,
                "contactPerson": contact_person,
                "establishmentYear": year,
                "gstNumber": gst,
                "image": image,
                "thumbs": thumbs,

                "coverage": u.get("coverage") or "Within District, Inter-District, Long Distance",
                "insurancePremium": u.get("insurancePremium") or "1% of declared value",
                "tracking": u.get("tracking") or "Live GPS Tracking",

                "tableRows": table_rows,
            }
            return {"ok": True, "data": data}

        return {"ok": False, "error": "Invalid buyer kind"}
