# backend/routes/root/root_routes.py

from flask import Blueprint, render_template

# Root blueprint
root_bp = Blueprint("root", __name__)


# -----------------------------
# PUBLIC HOME PAGE
# -----------------------------
@root_bp.get("/")
def home():
    """
    Render the public landing page.
    This replaces legacy backend.routes.home.home
    """
    return render_template("home.html")


# -----------------------------
# PUBLIC CONSUMER SCAN PAGE
# (Replaces legacy /consumer/scan)
# -----------------------------
@root_bp.get("/consumer/scan")
def consumer_scan_page():
    return render_template("consumer_scan.html")


# -----------------------------
# VIEW HISTORY PAGE
# (Used by traceability UI)
# -----------------------------
@root_bp.get("/view-history")
def view_history_page():
    return render_template("view_history.html")


# -----------------------------
# REGISTRATION SUCCESS PAGE
# -----------------------------
@root_bp.get("/registration-success")
def registration_success_page():
    return render_template("registration_success.html")
