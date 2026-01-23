# backend/routes/root/__init__.py

from flask import Blueprint

# Root / public-facing blueprint (minimal)
root_bp = Blueprint(
    "root",
    __name__,
    template_folder="../../templates",
    static_folder="../../static",
)

# Import routes to attach them to this blueprint
from . import root_routes  # noqa: E402,F401
