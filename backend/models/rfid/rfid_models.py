# backend/models/rfid/rfid_models.py

from __future__ import annotations

import re
from typing import List, Optional, Union

from pydantic import BaseModel, Field, validator

EXACT_HEX = 24  # typical EPC hex length


def _hex_clean(v: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", (v or "")).upper()


def normalize_epc(raw: str) -> str:
    """
    Accepts EPC with spaces/prefix/suffix from scanner/wedge.
    Returns exactly 24-hex EPC or "" if invalid.
    """
    c = _hex_clean(raw)
    if len(c) >= EXACT_HEX:
        return c[:EXACT_HEX]
    return ""


class RFIDBasePayload(BaseModel):
    userId: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)

    cropType: str = Field(..., min_length=1)
    cropId: str = Field(..., min_length=1)

    # optional, only because your contract signatures include crop_name
    cropName: Optional[str] = ""

    packagingDate: str = Field(..., min_length=1)
    expiryDate: str = Field(..., min_length=1)
    bagCapacity: str = Field(..., min_length=1)
    totalBags: Union[str, int] = Field(...)

    def total_bags_int(self) -> int:
        try:
            return int(str(self.totalBags).strip())
        except Exception:
            return 0


class RFIDSinglePayload(RFIDBasePayload):
    # accept single epc value
    epc: str = Field(..., min_length=1)

    def cleaned_epc(self) -> str:
        epc = normalize_epc(self.epc)
        if not epc:
            raise ValueError(f"bad_epc: {self.epc}")
        return epc


class RFIDListPayload(RFIDBasePayload):
    # accept list of epcs
    epcs: List[str] = Field(default_factory=list)

    @validator("epcs", pre=True)
    def _ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        raise ValueError("epcs must be a list of strings")

    def cleaned_epcs(self) -> List[str]:
        seen = set()
        out: List[str] = []
        for raw in self.epcs:
            epc = normalize_epc(str(raw))
            if not epc:
                raise ValueError(f"bad_epc: {raw}")
            if epc in seen:
                continue
            seen.add(epc)
            out.append(epc)
        return out
