# backend/routes/public_traceability.py
from flask import Blueprint, render_template, abort
from backend.services.traceability.traceability_services import TraceabilityService

public_trace_bp = Blueprint("public_trace_bp", __name__)  # no url_prefix

@public_trace_bp.get("/t/<token>")
def public_traceability(token):
    """
    Public journey page (no auth).
    token -> crop_id lookup -> build view model -> render your new template
    """
    crop_id = TraceabilityService.get_crop_id_by_public_token(token)
    if not crop_id:
        abort(404)

    vm = TraceabilityService.build_traceability_public(crop_id=crop_id)

    # Render your big template (the one you pasted)
    return render_template(
        "TraceabilityJourney.html",
        crop_id=crop_id,
        events_combined=vm.events_combined,
        product_image_url=vm.product_image_url,
        stage_images=getattr(vm, "stage_images", None),
        current_year=vm.current_year,
    )
