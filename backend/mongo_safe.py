# backend/mongo_safe.py
from __future__ import annotations

import os
from typing import Optional

# Prevent spamming logs on every request
_WARNED = False


def is_mongo_enabled() -> bool:
    """
    Mongo is enabled only when:
      - DISABLE_MONGO is NOT 1
      - USE_REMOTE_AUTH_API is NOT 1   (because in that mode you typically skip init_mongo)
    """
    if os.getenv("DISABLE_MONGO", "0") == "1":
        return False

    # If you're using Remote Auth API, Mongo may be intentionally not initialized.
    if os.getenv("USE_REMOTE_AUTH_API", "0") == "1":
        return False

    return True


def get_db() -> Optional[object]:
    """
    Returns mongo.db if initialized, else None.
    Safe to call anywhere (won't crash at import time).
    """
    global _WARNED

    if not is_mongo_enabled():
        return None

    try:
        from backend.mongo import mongo  # Flask-PyMongo instance
        db = getattr(mongo, "db", None)

        # If init_mongo(app) wasn't called, db will be None
        if db is None and not _WARNED:
            _WARNED = True
            print("⚠️ Mongo is enabled by env, but not initialized (mongo.db is None).")
        return db

    except Exception as e:
        if not _WARNED:
            _WARNED = True
            print(f"⚠️ Mongo unavailable: {e}")
        return None


def get_col(name: str):
    """
    Convenience helper:
      col = get_col("farm_coordinates")
      if not col: handle fallback
    """
    db = get_db()
    if db is None:
        return None
    try:
        return db[name]
    except Exception:
        return None
