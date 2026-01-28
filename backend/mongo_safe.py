# backend/mongo_safe.py
from __future__ import annotations

import os
from typing import Optional

_WARNED_DB = False
_WARNED_COLS = set()


def is_mongo_enabled() -> bool:
    """
    Mongo is enabled unless DISABLE_MONGO=1.
    NOTE: USE_REMOTE_AUTH_API does NOT disable Mongo.
    """
    return os.getenv("DISABLE_MONGO", "0") != "1"


def get_db() -> Optional[object]:
    """
    Returns mongo.db if initialized, else None.
    Safe to call anywhere.
    """
    global _WARNED_DB

    if not is_mongo_enabled():
        return None

    try:
        from backend.mongo import mongo  # Flask-PyMongo instance
        db = getattr(mongo, "db", None)

        if db is None and not _WARNED_DB:
            _WARNED_DB = True
            print("⚠️ Mongo enabled but NOT initialized (mongo.db is None). Did you call init_mongo(app)?")

        return db
    except Exception as e:
        if not _WARNED_DB:
            _WARNED_DB = True
            print(f"⚠️ Mongo unavailable: {e}")
        return None


def get_col(name: str):
    """
    Convenience helper: returns a collection object or None.
      col = get_col("users")
      if not col: fallback
    """
    db = get_db()
    if db is None:
        return None

    try:
        return db[name]
    except Exception as e:
        # warn once per collection
        if name not in _WARNED_COLS:
            _WARNED_COLS.add(name)
            print(f"⚠️ Mongo collection unavailable '{name}': {e}")
        return None
