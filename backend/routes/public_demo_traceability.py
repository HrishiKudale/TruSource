# backend/routes/public_demo_traceability.py
from __future__ import annotations

from datetime import datetime, timezone
from flask import Blueprint, render_template, abort

from backend.mongo_safe import get_col

public_demo_bp = Blueprint("public_demo_bp", __name__)  # no url_prefix


def _format_ts(ts):
    """Your dummy timestamp is epoch seconds."""
    if ts is None or ts == "":
        return ""
    try:
        ts = int(ts)
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts)


def _normalize_events(raw_events: list[dict]) -> list[dict]:
    """
    Converts api_cache.value items into what your TraceabilityJourney.html expects.
    Also fixes Sold -> Retail (your template uses 'Retail').
    Adds image_stage so your stage images work.
    """
    out = []

    for e in (raw_events or []):
        status = (e.get("status") or "").strip()
        stage = (e.get("stage") or "").strip() or None

        # Map your dummy "Sold" event into template's "Retail"
        if status.lower() == "sold":
            status = "Retail"
            stage = stage or "Sold"

        # Infer sub-stage for your template image selection
        image_stage = (e.get("image_stage") or "").strip().lower() or None
        if not image_stage:
            s = status.lower()
            if s == "planted":
                image_stage = "planted"
            elif s == "harvested":
                image_stage = "harvested"
            elif s == "processed":
                if e.get("receivedDate"):
                    image_stage = "processed_received"
                    stage = stage or "Received"
                elif e.get("processedDate"):
                    image_stage = "processed_processed"
                    stage = stage or "Processed"
                else:
                    image_stage = "processed"
            elif s == "distributed":
                if e.get("receivedDate"):
                    image_stage = "distributed_received"
                    stage = stage or "Received"
                elif e.get("processedDate") or e.get("dispatchDate"):
                    image_stage = "distributed_dispatched"
                    stage = stage or "Dispatched"
                else:
                    image_stage = "distributed"
            elif s == "retail":
                if e.get("receivedDate"):
                    image_stage = "retail_received"
                    stage = stage or "Received"
                else:
                    image_stage = "retail_sold"
                    stage = stage or "Sold"
            else:
                image_stage = s or "event"

        out.append({
            "status": status,
            "stage": stage,
            "image_stage": image_stage,

            "location": e.get("location") or "—",
            "actor": e.get("actor") or "—",
            "timestamp": _format_ts(e.get("timestamp")),

            "cropType": e.get("cropType") or "—",
            "cropId": e.get("cropId") or "—",
            "batchCode": e.get("batchCode") or "",

            # fields your template reads conditionally
            "datePlanted": e.get("datePlanted") or "",
            "harvestDate": e.get("harvestDate") or "",
            "receivedDate": e.get("receivedDate") or "",
            "processedDate": e.get("processedDate") or "",
            "packagingType": e.get("packagingType") or "",
            "harvesterName": e.get("harvesterName") or "",
            "harvestQuantity": e.get("harvestQuantity") or 0,
            "areaSize": e.get("areaSize") or 0,
            "processedQuantity": e.get("processedQuantity") or 0,

            # optional blockchain proof if you add later
            "tx_hash": e.get("tx_hash") or e.get("txHash") or "",
            "block_number": e.get("block_number") or e.get("blockNumber") or "",
        })

    # Sort by numeric timestamp if possible (oldest -> newest)
    def key(ev):
        # try to recover the original epoch from formatted string is hard,
        # so use raw timestamp if present in ev via tx fields — we don't have it now.
        return 0

    # Better: sort using original list order OR if raw had epoch, sort before formatting:
    # If your raw_events are already in order, we keep as-is.
    return out


@public_demo_bp.get("/traceability/journey/<crop_id>")
def public_demo_traceability(crop_id: str):
    """
    Public demo journey. Reads dummy data from api_cache:
      id = "crop_hist:<crop_id>"
      value = [events...]
    """
    api_cache = get_col("api_cache")
    if api_cache is None:
        abort(503)  # mongo not available

    doc = api_cache.find_one({"_id": f"crop_hist:{crop_id}"})

    if not doc:
        abort(404)

    events_combined = _normalize_events(doc.get("value") or [])
    if not events_combined:
        abort(404)

    return render_template(
        "TraceabilityJourney.html",   # <-- rename if your template file differs
        crop_id=crop_id,
        events_combined=events_combined,
        product_image_url=None,       # your template fallback handles images
        stage_images=None,
        current_year=datetime.now().year,
    )


@public_demo_bp.get("/traceability/ping")
def traceability_ping():
    api_cache = get_col("api_cache")
    if api_cache is None:
        return {"ok": False, "mongo": "not_initialized"}, 503
    return {"ok": True, "api_cache_docs": api_cache.count_documents({})}, 200
