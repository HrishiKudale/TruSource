# backend/services/auth_api_client.py

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests
from requests import Response

API_BASE = (os.getenv("AUTH_API_BASE_URL", "") or "").rstrip("/")


class AuthApiError(Exception):
    pass


# -----------------------------
# Config (tune if needed)
# -----------------------------
# Render cold start usually: first request fails or times out -> retry works
DEFAULT_TIMEOUT = 6           # per attempt
MAX_RETRIES = 3               # total attempts
BACKOFF_SECONDS = 1.5         # base delay between retries

# Warmup only once per process
_WARMED_UP = False


def _require_base():
    if not API_BASE:
        raise AuthApiError("AUTH_API_BASE_URL is not set")


def _is_retryable_status(code: int) -> bool:
    # Typical Render / upstream "not ready yet" statuses
    return code in (408, 429, 500, 502, 503, 504)


def _safe_json(r: Response) -> Dict[str, Any]:
    try:
        data = r.json()
        if isinstance(data, dict):
            return data
        return {"data": data}
    except Exception:
        # non-json (html error page, gateway error etc.)
        return {"message": f"Auth API returned non-JSON response ({r.status_code})"}


def _warmup_if_needed(session: requests.Session):
    """
    Hit /health once to wake the auth service on Render.
    If it fails, we don't hard-fail; the real call below will retry anyway.
    """
    global _WARMED_UP
    if _WARMED_UP:
        return

    _require_base()
    url = f"{API_BASE}/health"

    try:
        session.get(url, timeout=DEFAULT_TIMEOUT)
    except Exception:
        pass

    _WARMED_UP = True


def _request_with_retry(
    method: str,
    path: str,
    *,
    json_payload: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    _require_base()
    url = f"{API_BASE}{path}"

    with requests.Session() as s:
        # Warm-up (Render cold start)
        _warmup_if_needed(s)

        last_exc: Optional[Exception] = None
        last_data: Optional[dict] = None
        last_status: Optional[int] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = s.request(method, url, json=json_payload, timeout=timeout)
                last_status = r.status_code
                data = _safe_json(r)
                last_data = data

                # Success
                if 200 <= r.status_code < 300:
                    return data

                # Non-retryable auth errors -> fail fast
                if r.status_code in (400, 401, 403, 404):
                    msg = data.get("message") or data.get("detail") or "Request failed"
                    raise AuthApiError(msg)

                # Retryable errors -> retry
                if _is_retryable_status(r.status_code):
                    msg = data.get("message") or data.get("detail") or "Temporary auth service error"
                    last_exc = AuthApiError(f"{msg} (HTTP {r.status_code})")
                else:
                    # Other errors: treat as non-retryable
                    msg = data.get("message") or data.get("detail") or "Request failed"
                    raise AuthApiError(f"{msg} (HTTP {r.status_code})")

            except (requests.Timeout, requests.ConnectionError) as e:
                last_exc = e
            except AuthApiError:
                # already meaningful, don't wrap
                raise
            except Exception as e:
                last_exc = e

            # Retry backoff if not last attempt
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_SECONDS * attempt)

        # Exhausted retries
        if isinstance(last_exc, AuthApiError):
            raise last_exc

        # Provide a helpful message
        if last_status is not None:
            msg = (last_data or {}).get("message") or "Auth service unavailable"
            raise AuthApiError(f"{msg} (HTTP {last_status}) - please retry")
        raise AuthApiError(f"Auth service unreachable: {last_exc}")


def login(email: str, password: str, role: str | None = None) -> dict:
    payload = {"email": email, "password": password}
    if role:
        payload["role"] = role
    return _request_with_retry("POST", "/auth/login", json_payload=payload)


def register(payload: dict) -> dict:
    return _request_with_retry("POST", "/auth/register", json_payload=payload)


def refresh(refresh_token: str) -> dict:
    return _request_with_retry("POST", "/auth/refresh", json_payload={"refresh_token": refresh_token})
