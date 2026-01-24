# backend/services/auth_api_client.py
import os
import requests

API_BASE = os.getenv("AUTH_API_BASE_URL", "").rstrip("/")

class AuthApiError(Exception):
    pass

def _post(path: str, payload: dict, timeout: int = 20) -> dict:
    if not API_BASE:
        raise AuthApiError("AUTH_API_BASE_URL is not set")

    url = f"{API_BASE}{path}"
    r = requests.post(url, json=payload, timeout=timeout)

    # API returns JSON always
    try:
        data = r.json()
    except Exception:
        raise AuthApiError(f"Auth API returned non-JSON response ({r.status_code})")

    if r.status_code >= 400:
        msg = data.get("message") or data.get("detail") or "Request failed"
        raise AuthApiError(msg)

    return data

def login(email: str, password: str, role: str | None = None) -> dict:
    payload = {"email": email, "password": password}
    if role:
        payload["role"] = role
    return _post("/auth/login", payload)

def register(payload: dict) -> dict:
    return _post("/auth/register", payload)

def refresh(refresh_token: str) -> dict:
    # If you implement refresh as Bearer token in headers, adapt later
    return _post("/auth/refresh", {"refresh_token": refresh_token})
