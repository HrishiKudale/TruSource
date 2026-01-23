# backend/routes/traceability/__init__.py

from flask import Blueprint

trace_bp = Blueprint(
    "traceability",
    __name__,
    url_prefix="/trace",
    template_folder="../../templates",
    static_folder="../../static",
)

from . import trace_routes  # noqa
