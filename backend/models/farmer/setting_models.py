# backend/models/settings_models.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProfileUpdatePayload:
    name: str
    email: str
    phone: str


@dataclass
class PasswordUpdatePayload:
    currentPassword: str
    newPassword: str
    confirmPassword: str


@dataclass
class PreferencesPayload:
    language: Optional[str] = None
    harvestNotifications: Optional[bool] = None
