# backend/services/rfid_service.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo.errors import DuplicateKeyError

from backend.mongo_safe import get_col
from backend.models.rfid.rfid_models import (
    RFIDSinglePayload,
    RFIDListPayload,
    normalize_epc,
)

from backend.blockchain import (
    register_rfid_onchain_single,
    register_rfids_onchain,
    get_rfid_epcs_by_crop,
    get_rfid_record,
)


class RFIDService:
    COL = "rfid_records"

    # ------------------------------------------------------------
    # Entry point (AUTO): supports payload having either `epc` OR `epcs`
    # ------------------------------------------------------------
    @staticmethod
    def register_auto(payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        If payload has:
          - "epc" -> single flow
          - "epcs" -> list flow
        """
        if "epc" in payload_dict and str(payload_dict.get("epc") or "").strip():
            return RFIDService.register_single_epc(payload_dict)

        if "epcs" in payload_dict and isinstance(payload_dict.get("epcs"), list):
            return RFIDService.register_epc_list(payload_dict)

        return {"ok": False, "err": "Send either 'epc' (single) or 'epcs' (list)."}

    # ------------------------------------------------------------
    # Single EPC flow (Mongo + chain)
    # ------------------------------------------------------------
    @staticmethod
    def register_single_epc(payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        p = RFIDSinglePayload(**payload_dict)
        epc = p.cleaned_epc()

        col = get_col(RFIDService.COL)
        if col is None:
            return {"ok": False, "err": "MongoDB is disabled or unavailable"}

        RFIDService._ensure_indexes(col)

        # Optional chain duplicate check (fast guard)
        if RFIDService._epc_exists_on_chain(p.cropId, epc):
            RFIDService._upsert_doc(col, p, epc, status="MINED", tx_hash=None, error=None)
            return {"ok": True, "cropId": p.cropId, "rfidEPC": epc, "status": "MINED", "note": "Already on-chain"}

        # Save as pending in Mongo
        RFIDService._upsert_doc(col, p, epc, status="PENDING", tx_hash=None, error=None)

        # Chain tx (single)
        try:
            txh = register_rfid_onchain_single(
                user_id=p.userId,
                username=p.username,
                crop_name=(p.cropName or ""),
                crop_type=p.cropType,
                crop_id=p.cropId,
                packaging_date=p.packagingDate,
                expiry_date=p.expiryDate,
                bag_capacity=p.bagCapacity,
                total_bags=str(p.total_bags_int() or 1),
                rfid_epc=epc,
            )

            RFIDService._upsert_doc(col, p, epc, status="MINED", tx_hash=txh, error=None)
            return {"ok": True, "cropId": p.cropId, "rfidEPC": epc, "status": "MINED", "txHash": txh}

        except Exception as e:
            msg = str(e)
            RFIDService._upsert_doc(col, p, epc, status="FAILED", tx_hash=None, error=msg)
            return {"ok": False, "cropId": p.cropId, "rfidEPC": epc, "status": "FAILED", "error": msg}

    # ------------------------------------------------------------
    # List EPC flow (Mongo + chain, uses bulk tx ideally)
    # ------------------------------------------------------------
    @staticmethod
    def register_epc_list(payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        p = RFIDListPayload(**payload_dict)
        epcs = p.cleaned_epcs()

        if not epcs:
            return {"ok": False, "err": "Scan at least 1 EPC"}

        tb = p.total_bags_int()
        if tb > 0 and len(epcs) != tb:
            return {"ok": False, "err": f"Scan exactly {tb} EPC(s). Currently: {len(epcs)}"}

        col = get_col(RFIDService.COL)
        if col is None:
            return {"ok": False, "err": "MongoDB is disabled or unavailable"}

        RFIDService._ensure_indexes(col)

        # Optional: prevent duplicates already on chain for this crop
        existing_chain = RFIDService._chain_epcs_set(p.cropId)
        for epc in epcs:
            if epc in existing_chain:
                return {"ok": False, "err": f"epc_already_registered: {epc}"}

        # Save all as PENDING in Mongo (upsert)
        for epc in epcs:
            RFIDService._upsert_doc(col, p, epc, status="PENDING", tx_hash=None, error=None)

        # Chain bulk tx
        try:
            txh = register_rfids_onchain(
                user_id=p.userId,
                username=p.username,
                crop_name=(p.cropName or ""),
                crop_type=p.cropType,
                crop_id=p.cropId,
                packaging_date=p.packagingDate,
                expiry_date=p.expiryDate,
                bag_capacity=p.bagCapacity,
                total_bags=str(tb if tb else len(epcs)),
                epcs=epcs,
            )

            # mark all mined with same tx hash
            RFIDService._bulk_update(col, p.cropId, epcs, status="MINED", tx_hash=txh, error=None)

            return {
                "ok": True,
                "cropId": p.cropId,
                "count": len(epcs),
                "txHash": txh,
                "results": [{"rfidEPC": e, "status": "MINED", "txHash": txh} for e in epcs],
            }

        except Exception as bulk_err:
            # If bulk fails, you can choose:
            # A) return fail and keep Mongo pending/failed
            # B) fallback to single tx per epc (recommended)
            bulk_msg = str(bulk_err)

            results = []
            for epc in epcs:
                try:
                    tx1 = register_rfid_onchain_single(
                        user_id=p.userId,
                        username=p.username,
                        crop_name=(p.cropName or ""),
                        crop_type=p.cropType,
                        crop_id=p.cropId,
                        packaging_date=p.packagingDate,
                        expiry_date=p.expiryDate,
                        bag_capacity=p.bagCapacity,
                        total_bags=str(tb if tb else len(epcs)),
                        rfid_epc=epc,
                    )
                    RFIDService._update_one(col, p.cropId, epc, status="MINED", tx_hash=tx1, error=None)
                    results.append({"rfidEPC": epc, "status": "MINED", "txHash": tx1})
                except Exception as e:
                    msg = str(e)
                    RFIDService._update_one(col, p.cropId, epc, status="FAILED", tx_hash=None, error=msg)
                    results.append({"rfidEPC": epc, "status": "FAILED", "error": msg})

            return {
                "ok": False,  # bulk failed, but some may succeed in fallback
                "cropId": p.cropId,
                "count": len(results),
                "note": f"Bulk tx failed; fallback per EPC used. bulk_error={bulk_msg}",
                "results": results,
            }

    # ------------------------------------------------------------
    # Read APIs
    # ------------------------------------------------------------
    @staticmethod
    def fetch_rfid_list(crop_id: str) -> Dict[str, Any]:
        col = get_col(RFIDService.COL)
        if col is None:
            return {"ok": False, "err": "MongoDB unavailable"}

        docs = list(col.find({"crop_id": crop_id}, {"_id": 0}))
        return {"ok": True, "cropId": crop_id, "records": docs}

    @staticmethod
    def fetch_rfid_details(crop_id: str, epc: str) -> Dict[str, Any]:
        col = get_col(RFIDService.COL)
        if col is None:
            return {"ok": False, "err": "MongoDB unavailable"}

        epc = normalize_epc(epc)
        if not epc:
            return {"ok": False, "err": "bad_epc"}

        doc = col.find_one({"crop_id": crop_id, "rfid_epc": epc}, {"_id": 0})
        chain = None
        try:
            chain = get_rfid_record(crop_id, epc)
        except Exception:
            chain = None

        return {"ok": True, "cropId": crop_id, "rfidEPC": epc, "mongo": doc, "chain": chain}

    # ------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------
    @staticmethod
    def _ensure_indexes(col):
        try:
            col.create_index([("crop_id", 1), ("rfid_epc", 1)], unique=True, name="uq_crop_epc")
            col.create_index([("crop_id", 1)], name="idx_crop")
            col.create_index([("user_id", 1)], name="idx_user")
        except Exception:
            pass

    @staticmethod
    def _chain_epcs_set(crop_id: str) -> set:
        try:
            return set(get_rfid_epcs_by_crop(crop_id) or [])
        except Exception:
            return set()

    @staticmethod
    def _epc_exists_on_chain(crop_id: str, epc: str) -> bool:
        try:
            existing = set(get_rfid_epcs_by_crop(crop_id) or [])
            return epc in existing
        except Exception:
            return False

    @staticmethod
    def _upsert_doc(col, p, epc: str, status: str, tx_hash: Optional[str], error: Optional[str]):
        now = datetime.utcnow()
        doc = {
            "crop_id": p.cropId,
            "user_id": p.userId,
            "username": p.username,
            "crop_type": p.cropType,
            "crop_name": (getattr(p, "cropName", "") or "").strip(),
            "packaging_date": p.packagingDate,
            "expiry_date": p.expiryDate,
            "bag_capacity": p.bagCapacity,
            "total_bags": str(p.total_bags_int() or 0),
            "rfid_epc": epc,
            "status": status,
            "txHash": tx_hash,
            "error_message": error,
            "updated_at": now,
        }
        try:
            col.update_one(
                {"crop_id": p.cropId, "rfid_epc": epc},
                {"$set": doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
        except DuplicateKeyError:
            # If it exists due to unique index, just update status fields
            col.update_one(
                {"crop_id": p.cropId, "rfid_epc": epc},
                {"$set": {"status": status, "txHash": tx_hash, "error_message": error, "updated_at": now}},
            )

    @staticmethod
    def _update_one(col, crop_id: str, epc: str, status: str, tx_hash: Optional[str], error: Optional[str]):
        now = datetime.utcnow()
        col.update_one(
            {"crop_id": crop_id, "rfid_epc": epc},
            {"$set": {"status": status, "txHash": tx_hash, "error_message": error, "updated_at": now}},
        )

    @staticmethod
    def _bulk_update(col, crop_id: str, epcs: List[str], status: str, tx_hash: Optional[str], error: Optional[str]):
        now = datetime.utcnow()
        col.update_many(
            {"crop_id": crop_id, "rfid_epc": {"$in": epcs}},
            {"$set": {"status": status, "txHash": tx_hash, "error_message": error, "updated_at": now}},
        )
