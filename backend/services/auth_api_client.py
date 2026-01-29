# backend/services/auth_api_client.py
from __future__ import annotations

import os
import time
import threading
import requests
from typing import Any, Dict, Optional

API_BASE = (os.getenv("AUTH_API_BASE_URL", "") or "").rstrip("/")

DEFAULT_TIMEOUT = int(os.getenv("AUTH_API_TIMEOUT", "15"))
WARMUP_TIMEOUT = int(os.getenv("AUTH_API_WARMUP_TIMEOUT", "6"))
MAX_RETRIES = int(os.getenv("AUTH_API_MAX_RETRIES", "3"))

# Render transient / cold start
RETRY_STATUS = {502, 503, 504}

# Warmup cache (avoid calling /health for every request)
WARMUP_EVERY_SECONDS = int(os.getenv("AUTH_API_WARMUP_EVERY_SECONDS", "600"))  # 10 min

class AuthApiError(Exception):
    pass

# Reuse connections (reduces overhead)
_session = requests.Session()

# Warmup state
_warm_lock = threading.Lock()
_last_warm_at = 0.0

def _ensure_base() -> None:
    if not API_BASE:
        raise AuthApiError("AUTH_API_BASE_URL is not set")

def _safe_json(resp: requests.Response) -> Optional[Dict[str, Any]]:
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {"data": data}
    except Exception:
        return None

def warmup(force: bool = False) -> None:
    """
    Wake Render service by calling /health, but not on every request.
    """
    global _last_warm_at
    _ensure_base()

    now = time.time()
    if not force and (now - _last_warm_at) < WARMUP_EVERY_SECONDS:
        return

    with _warm_lock:
        # double-check after lock
        now = time.time()
        if not force and (now - _last_warm_at) < WARMUP_EVERY_SECONDS:
            return

        try:
            _session.get(f"{API_BASE}/health", timeout=WARMUP_TIMEOUT, allow_redirects=True)
        except Exception:
            # ignore warmup failure; actual request will retry
            pass
        finally:
            _last_warm_at = time.time()

def _post(path: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    _ensure_base()

    # Warmup once in a while, not every request
    warmup(force=False)

    url = f"{API_BASE}{path}"
    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = _session.post(url, json=payload, timeout=timeout, allow_redirects=True)

            if resp.status_code in RETRY_STATUS:
                last_err = f"Upstream error {resp.status_code}"
                time.sleep(min(0.6 * (2 ** (attempt - 1)), 3.0))
                continue

            data = _safe_json(resp)

            if data is None:
                snippet = (resp.text or "").strip().replace("\n", " ")[:200]
                raise AuthApiError(f"Auth API returned non-JSON response ({resp.status_code}): {snippet}")

            if resp.status_code >= 400:
                msg = data.get("message") or data.get("detail") or data.get("error") or "Request failed"
                raise AuthApiError(f"{msg} (HTTP {resp.status_code})")

            return data

        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = f"Network error: {e}"
            time.sleep(min(0.6 * (2 ** (attempt - 1)), 3.0))
            continue

    raise AuthApiError(f"Auth API failed after {MAX_RETRIES} retries: {last_err}")

def login(email: str, password: str, role: str | None = None) -> Dict[str, Any]:
    payload = {"email": email, "password": password}
    if role:
        payload["role"] = role
    return _post("/auth/login", payload)

def register(payload: dict) -> Dict[str, Any]:
    return _post("/auth/register", payload)

def refresh(refresh_token: str) -> Dict[str, Any]:
    return _post("/auth/refresh", {"refresh_token": refresh_token})
