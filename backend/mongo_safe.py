# backend/mongo_safe.py
from __future__ import annotations
import os
from typing import Optional

def is_mongo_enabled() -> bool:
    # If you want to disable Mongo completely on Render:
    # DISABLE_MONGO=1
    return os.getenv("DISABLE_MONGO", "0") != "1"

def get_db() -> Optional[object]:
    """
    Returns mongo.db if initialized, else None.
    Never throws import-time errors.
    """
    if not is_mongo_enabled():
        return None

    try:
        from backend.mongo import mongo  # your Flask-PyMongo instance
        return getattr(mongo, "db", None)
    except Exception:
        return None
