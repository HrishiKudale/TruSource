# backend/services/auth_api_client.py
from __future__ import annotations

import os
import time
import requests
from typing import Any, Dict, Optional

API_BASE = (os.getenv("AUTH_API_BASE_URL", "") or "").rstrip("/")

DEFAULT_TIMEOUT = int(os.getenv("AUTH_API_TIMEOUT", "30"))          # per request
WARMUP_TIMEOUT  = int(os.getenv("AUTH_API_WARMUP_TIMEOUT", "8"))    # per warmup ping
WARMUP_MAX_WAIT = int(os.getenv("AUTH_API_WARMUP_MAX_WAIT", "25"))  # total warmup time
MAX_RETRIES     = int(os.getenv("AUTH_API_MAX_RETRIES", "6"))

RETRY_STATUS = {502, 503, 504}

# keep service warmup state in-memory (per gunicorn worker)
_WARMED_UNTIL = 0.0  # epoch seconds


class AuthApiError(Exception):
    pass


def _ensure_base():
    if not API_BASE:
        raise AuthApiError("AUTH_API_BASE_URL is not set")


def _safe_json(resp: requests.Response) -> Optional[Dict[str, Any]]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}
    except Exception:
        return None


def warmup(force: bool = False) -> bool:
    """
    BLOCKING warmup:
    - keep pinging /health until it returns 200 OR until WARMUP_MAX_WAIT is reached.
    - caches success for ~2 minutes to avoid doing this on every request.
    """
    global _WARMED_UNTIL
    _ensure_base()

    now = time.time()
    if not force and now < _WARMED_UNTIL:
        return True

    url = f"{API_BASE}/health"
    start = now
    delay = 0.8

    while True:
        try:
            r = requests.get(url, timeout=WARMUP_TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                _WARMED_UNTIL = time.time() + 120  # cache warm state for 2 minutes
                return True
        except Exception:
            pass

        if (time.time() - start) >= WARMUP_MAX_WAIT:
            return False

        time.sleep(delay)
        delay = min(delay * 1.4, 3.0)


def _post(path: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """
    Single base only:
      API_BASE + /auth/login
      API_BASE + /auth/register
    Retry:
      - 502/503/504
      - connection/timeouts
    """
    _ensure_base()

    # Try to wake auth service (best-effort; request loop will still handle)
    warmup(force=False)

    url = f"{API_BASE}{path}"
    last_err: Optional[str] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=timeout, allow_redirects=True)

            # Cold start / gateway errors
            if resp.status_code in RETRY_STATUS:
                last_err = f"Upstream error {resp.status_code}"
                time.sleep(min(0.8 * attempt, 4.0))
                continue

            data = _safe_json(resp)
            if data is None:
                snippet = (resp.text or "").strip().replace("\n", " ")[:240]
                raise AuthApiError(f"Auth API returned non-JSON ({resp.status_code}): {snippet}")

            if resp.status_code >= 400:
                msg = data.get("message") or data.get("detail") or data.get("error") or "Request failed"
                raise AuthApiError(f"{msg} (HTTP {resp.status_code})")

            return data

        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = f"Network error: {e}"
            time.sleep(min(0.8 * attempt, 4.0))
            continue

    raise AuthApiError(f"Auth API not responding at {url}. Last: {last_err}")


def login(email: str, password: str, role: str) -> Dict[str, Any]:
    return _post("/auth/login", {"email": email, "password": password, "role": role})


def register(payload: dict) -> Dict[str, Any]:
    # IMPORTANT: payload must include userId if your auth_api enforces it
    return _post("/auth/register", payload)
