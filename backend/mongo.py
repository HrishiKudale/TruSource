# backend/mongo.py
from __future__ import annotations

import os
from flask_pymongo import PyMongo

mongo = PyMongo()


def init_mongo(app):
    """
    Initializes Flask-PyMongo.
    Requires app.config["MONGO_URI"] or env var MONGO_URI.
    Call this during app startup (create_app).
    """

    # If app.config doesn't have MONGO_URI, try env var
    if not app.config.get("MONGO_URI"):
        app.config["MONGO_URI"] = os.getenv("MONGO_URI")

    # If still missing, don't crash the app—log and leave mongo uninitialized
    if not app.config.get("MONGO_URI"):
        print("⚠️ MONGO_URI not set. Mongo will not be initialized.")
        return mongo

    try:
        mongo.init_app(app)

        # sanity ping (this can still fail if URI is wrong)
        _ = mongo.db  # triggers db property
        print("✅ Mongo initialized")
    except Exception as e:
        # don't crash startup; keep app running (you will see mongo_safe warnings later)
        print(f"⚠️ Mongo init failed: {e}")

    return mongo
