# backend/services/auth_api_client.py
from __future__ import annotations

import os
import time
import requests
from typing import Any, Dict, Optional

API_BASE = (os.getenv("AUTH_API_BASE_URL", "") or "").rstrip("/")

# Tunables (safe defaults for Render cold starts)
DEFAULT_TIMEOUT = int(os.getenv("AUTH_API_TIMEOUT", "20"))  # seconds
WARMUP_TIMEOUT = int(os.getenv("AUTH_API_WARMUP_TIMEOUT", "8"))
MAX_RETRIES = int(os.getenv("AUTH_API_MAX_RETRIES", "3"))

# Retry these (typical transient / cold start / gateway)
RETRY_STATUS = {502, 503, 504}


class AuthApiError(Exception):
    pass


def _ensure_base():
    if not API_BASE:
        raise AuthApiError("AUTH_API_BASE_URL is not set")


def _safe_json(resp: requests.Response) -> Optional[Dict[str, Any]]:
    """
    Return JSON dict if response is JSON, else None.
    Render 502 often returns HTML -> must not crash json().
    """
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype:
        try:
            data = resp.json()
            if isinstance(data, dict):
                return data
            # If it's a list etc, wrap
            return {"data": data}
        except Exception:
            return None

    # Some services return JSON without correct header
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {"data": data}
    except Exception:
        return None


def _warmup() -> None:
    """
    Ping /health once (or a few times) to wake Render service.
    We ignore failures here; main request handles retry anyway.
    """
    _ensure_base()
    url = f"{API_BASE}/health"
    try:
        requests.get(url, timeout=WARMUP_TIMEOUT)
    except Exception:
        pass


def _post(path: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """
    POST with:
      - warmup for Render cold-start
      - retry on 502/503/504 and network timeouts
      - safe JSON parsing (handle HTML 502 pages)
    """
    _ensure_base()
    _warmup()

    url = f"{API_BASE}{path}"
    last_err: Optional[str] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)

            # Retry transient gateway errors
            if resp.status_code in RETRY_STATUS:
                last_err = f"Upstream error {resp.status_code}"
                # exponential backoff: 0.6, 1.2, 2.4 ...
                time.sleep(0.6 * (2 ** (attempt - 1)))
                continue

            data = _safe_json(resp)

            # If server didn't return JSON, show short snippet to help debug
            if data is None:
                snippet = (resp.text or "").strip().replace("\n", " ")[:240]
                raise AuthApiError(
                    f"Auth API returned non-JSON response ({resp.status_code}): {snippet}"
                )

            # If error status, raise with best message we can extract
            if resp.status_code >= 400:
                msg = (
                    data.get("message")
                    or data.get("detail")
                    or data.get("error")
                    or "Request failed"
                )
                raise AuthApiError(f"{msg} (HTTP {resp.status_code})")

            return data

        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = f"Network error: {e}"
            if attempt < MAX_RETRIES:
                time.sleep(0.6 * (2 ** (attempt - 1)))
                continue
            raise AuthApiError(f"Auth API unreachable: {last_err}")

        except AuthApiError:
            # if it's a deliberate error, don't retry unless it's a retry status
            raise

        except Exception as e:
            last_err = str(e)
            if attempt < MAX_RETRIES:
                time.sleep(0.6 * (2 ** (attempt - 1)))
                continue
            raise AuthApiError(f"Auth API error: {last_err}")

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
