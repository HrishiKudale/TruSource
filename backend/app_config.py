# backend/app_config.py

import os

def load_config(app):
    """
    Load all Flask configuration in a clean centralized way.
    """
    # ------------------------------
    # Mongo
    # ------------------------------
    app.config["MONGO_URI"] = os.getenv(
        "MONGO_URI",
        "mongodb://localhost:27017/crop_traceability_db"
    )

    # ------------------------------
    # Blockchain Settings
    # ------------------------------
    app.config["RECALL_REGISTRY_ADDRESS"] = os.getenv(
        "RECALL_REGISTRY_ADDRESS",
        "0x888332F60954778ca8ff945C2f44F662E089fb8A"
    )

    # ------------------------------
    # Security Keys
    # ------------------------------
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(24))

    print("✓ Config Loaded Successfully")
