# backend/services/auth_api_client.py
from __future__ import annotations

import os
import time
import requests
from typing import Any, Dict, Optional, List

API_BASE = (os.getenv("AUTH_API_BASE_URL", "") or "").rstrip("/")

# Tunables for Render cold starts
DEFAULT_TIMEOUT = int(os.getenv("AUTH_API_TIMEOUT", "20"))
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
    Return JSON dict if response body is JSON, else None.
    Handles HTML (Render 502/404 pages) safely.
    """
    # Try header-based check
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype:
        try:
            data = resp.json()
            return data if isinstance(data, dict) else {"data": data}
        except Exception:
            return None

    # Some services return JSON without correct content-type
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}
    except Exception:
        return None


def _candidate_bases() -> List[str]:
    """
    Support common deployments:
      - https://service.onrender.com
      - https://service.onrender.com/api
    If user already set /api in base, don't double it.
    """
    base = API_BASE.rstrip("/")
    if base.endswith("/api"):
        return [base]  # already includes /api
    return [base, base + "/api"]


def _warmup() -> None:
    """
    Ping health endpoints to wake Render service.
    Try both /health and /api/health depending on mount style.
    Ignore failures (main request handles retry).
    """
    _ensure_base()
    for b in _candidate_bases():
        url = f"{b}/health"
        try:
            requests.get(url, timeout=WARMUP_TIMEOUT, allow_redirects=True)
            return  # one successful warmup is enough
        except Exception:
            pass


def _post_any(path: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """
    POST with:
      - warmup for Render cold-start
      - retry on 502/503/504 and network timeouts
      - path fallback: tries {base}{path} and {base}/api{path} depending on AUTH_API_BASE_URL
      - safe JSON parsing (handle HTML 404/502 pages)
    """
    _ensure_base()
    _warmup()

    # Build candidate URLs
    urls: List[str] = []
    for b in _candidate_bases():
        urls.append(f"{b}{path}")

    last_err: Optional[str] = None

    for url in urls:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(url, json=payload, timeout=timeout, allow_redirects=True)

                # Retry transient gateway errors
                if resp.status_code in RETRY_STATUS:
                    last_err = f"Upstream error {resp.status_code} on {url}"
                    time.sleep(0.6 * (2 ** (attempt - 1)))
                    continue

                data = _safe_json(resp)

                # If server didn't return JSON
                if data is None:
                    snippet = (resp.text or "").strip().replace("\n", " ")[:240]
                    # If it's 404 HTML, try next candidate URL
                    if resp.status_code == 404:
                        last_err = f"404 Not Found on {url}: {snippet}"
                        break
                    raise AuthApiError(f"Auth API returned non-JSON response ({resp.status_code}) on {url}: {snippet}")

                # If error status, raise with message
                if resp.status_code >= 400:
                    msg = data.get("message") or data.get("detail") or data.get("error") or "Request failed"
                    # If 404 from JSON, try next candidate URL
                    if resp.status_code == 404:
                        last_err = f"{msg} (HTTP 404) on {url}"
                        break
                    raise AuthApiError(f"{msg} (HTTP {resp.status_code})")

                return data

            except (requests.Timeout, requests.ConnectionError) as e:
                last_err = f"Network error on {url}: {e}"
                if attempt < MAX_RETRIES:
                    time.sleep(0.6 * (2 ** (attempt - 1)))
                    continue
                # network error on this url → try next url
                break

            except AuthApiError:
                raise

            except Exception as e:
                last_err = f"Unexpected error on {url}: {e}"
                if attempt < MAX_RETRIES:
                    time.sleep(0.6 * (2 ** (attempt - 1)))
                    continue
                break

    tried = ", ".join(urls)
    raise AuthApiError(
        f"Auth API endpoint not found / not responding. Tried: {tried}. Last: {last_err}"
    )


def login(email: str, password: str, role: str | None = None) -> Dict[str, Any]:
    payload = {"email": email, "password": password}
    if role:
        payload["role"] = role
    return _post_any("/auth/login", payload)


def register(payload: dict) -> Dict[str, Any]:
    return _post_any("/auth/register", payload)


def refresh(refresh_token: str) -> Dict[str, Any]:
    return _post_any("/auth/refresh", {"refresh_token": refresh_token})
