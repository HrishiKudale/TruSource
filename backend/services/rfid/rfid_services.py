# services/rfid_service.py
from dataclasses import dataclass
from typing import Any, Dict, List

from web3.exceptions import ContractLogicError

# ✅ Reuse your working blockchain wiring
from backend.blockchain import web3, account, contract, suggest_fees

from backend.models.rfid.rfid_models import db, RFIDRecord


def _raw_tx_bytes(signed) -> bytes:
    """
    eth-account compatibility helper:
    supports signed.rawTransaction / raw_transaction / dict styles.
    """
    raw = getattr(signed, "rawTransaction", None)
    if raw is None:
        raw = getattr(signed, "raw_transaction", None)
    if raw is None and isinstance(signed, dict):
        raw = signed.get("rawTransaction") or signed.get("raw_transaction")
    if raw is None:
        raise TypeError("SignedTransaction has no raw tx bytes")
    return raw


@dataclass
class RFIDPayload:
    userId: str
    username: str
    cropType: str
    cropId: str
    packagingDate: str
    expiryDate: str
    bagCapacity: str
    totalBags: str
    epcs: List[str]


class RFIDService:
    @staticmethod
    def register_rfids(payload: RFIDPayload) -> Dict[str, Any]:
        RFIDService._validate(payload)

        # clean + dedupe epcs
        epcs = RFIDService._dedupe(payload.epcs)
        results = []

        for epc in epcs:
            results.append(RFIDService._register_single(payload, epc))

        return {
            "ok": True,
            "cropId": payload.cropId,
            "count": len(results),
            "results": results,
        }

    # ---------------------------------------
    # Internals
    # ---------------------------------------
    @staticmethod
    def _validate(p: RFIDPayload):
        fields = {
            "userId": p.userId,
            "username": p.username,
            "cropType": p.cropType,
            "cropId": p.cropId,
            "packagingDate": p.packagingDate,
            "expiryDate": p.expiryDate,
            "bagCapacity": p.bagCapacity,
            "totalBags": p.totalBags,
        }
        for k, v in fields.items():
            if not str(v or "").strip():
                raise ValueError(f"{k} is required")

        if not isinstance(p.epcs, list) or len(p.epcs) == 0:
            raise ValueError("epcs must be a non-empty list")

    @staticmethod
    def _dedupe(epcs: List[str]) -> List[str]:
        seen = set()
        out = []
        for e in epcs:
            e = str(e or "").strip()
            if not e:
                continue
            if e in seen:
                continue
            seen.add(e)
            out.append(e)
        return out

    @staticmethod
    def _register_single(p: RFIDPayload, epc: str) -> Dict[str, Any]:
        # ✅ local record to avoid duplicates
        existing = RFIDRecord.query.filter_by(crop_id=p.cropId, rfid_epc=epc).first()
        if existing and existing.status in ("PENDING", "MINED"):
            return {
                "rfidEPC": epc,
                "status": existing.status,
                "txHash": existing.tx_hash,
                "note": "Already exists locally for this crop",
            }

        # create pending record
        rec = existing or RFIDRecord(
            crop_id=p.cropId,
            user_id=p.userId,
            username=p.username,
            crop_type=p.cropType,
            packaging_date=p.packagingDate,
            expiry_date=p.expiryDate,
            bag_capacity=p.bagCapacity,
            total_bags=p.totalBags,
            rfid_epc=epc,
            status="PENDING",
        )
        if not existing:
            db.session.add(rec)
            db.session.commit()

        try:
            # ✅ optional on-chain duplicate guard (your contract has hasRFID)
            try:
                already = contract.functions.hasRFID(p.cropId, epc).call()
                if already:
                    rec.status = "MINED"
                    rec.error_message = None
                    db.session.commit()
                    return {"rfidEPC": epc, "status": "MINED", "note": "Already registered on-chain"}
            except Exception:
                # if hasRFID isn't available or fails, continue (contract will revert duplicates anyway)
                pass

            fn = contract.functions.registerRFIDs(
                p.userId,
                p.username,
                p.cropType,
                p.cropId,
                p.packagingDate,
                p.expiryDate,
                p.bagCapacity,
                p.totalBags,
                epc,
            )

            gas_est = fn.estimate_gas({"from": account.address})
            prio, max_fee = suggest_fees()

            tx = fn.build_transaction(
                {
                    "from": account.address,
                    "nonce": web3.eth.get_transaction_count(account.address, "pending"),
                    "chainId": 80002,  # Polygon Amoy (same as your crop/harvest)
                    "gas": int(gas_est * 1.20),
                    "maxPriorityFeePerGas": prio,
                    "maxFeePerGas": max_fee,
                }
            )

            signed = account.sign_transaction(tx)
            raw_tx = _raw_tx_bytes(signed)

            tx_hash = web3.eth.send_raw_transaction(raw_tx).hex()

            rec.tx_hash = tx_hash
            rec.status = "PENDING"
            rec.error_message = None
            db.session.commit()

            # wait receipt (recommended for UI correctness)
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt and receipt.status == 1:
                rec.status = "MINED"
                db.session.commit()
                return {"rfidEPC": epc, "status": "MINED", "txHash": tx_hash}
            else:
                rec.status = "FAILED"
                rec.error_message = "Transaction failed/reverted"
                db.session.commit()
                return {"rfidEPC": epc, "status": "FAILED", "txHash": tx_hash, "error": rec.error_message}

        except ContractLogicError as e:
            msg = str(e)
            rec.status = "FAILED"
            rec.error_message = msg
            db.session.commit()
            return {"rfidEPC": epc, "status": "FAILED", "error": msg}

        except Exception as e:
            msg = str(e)
            rec.status = "FAILED"
            rec.error_message = msg
            db.session.commit()
            return {"rfidEPC": epc, "status": "FAILED", "error": msg}





# backend/rfid_service.py
import re
from typing import Dict, Any, List, Tuple
from backend.blockchain import register_rfids_onchain, get_rfid_epcs_by_crop, get_rfid_record

EXACT_HEX = 24  # typical EPC length (your Mongo code used this)

def _hex_clean(v: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", (v or "")).upper()

def normalize_epc(raw: str) -> str:
    """
    Accepts:
      - Already clean EPC
      - Wedge input with spaces, prefix, suffix, etc.
    Returns 24-hex EPC if possible, else empty string.
    """
    c = _hex_clean(raw)
    if len(c) >= EXACT_HEX:
        return c[:EXACT_HEX]
    return ""

def register_epcs_onchain(payload: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    # Required fields
    user_id = (payload.get("userId") or "").strip()
    username = (payload.get("username") or "").strip()
    crop_type = (payload.get("cropType") or "").strip()
    crop_id = (payload.get("cropId") or "").strip()

    packaging_date = (payload.get("packagingDate") or "").strip()
    expiry_date = (payload.get("expiryDate") or "").strip()
    bag_capacity = (payload.get("bagCapacity") or "").strip()
    total_bags = str(payload.get("totalBags") or "").strip()

    epcs_in = payload.get("epcs") or []
    if isinstance(epcs_in, str):
      # if someone passed JSON string
      epcs_in = []

    if not user_id: return False, "userId required", {}
    if not username: return False, "username required", {}
    if not crop_id: return False, "cropId required", {}
    if not crop_type: return False, "cropType required", {}
    if not packaging_date: return False, "packagingDate required", {}
    if not expiry_date: return False, "expiryDate required", {}
    if not bag_capacity: return False, "bagCapacity required", {}
    if not total_bags: return False, "totalBags required", {}

    # Normalize EPCs + de-dup
    cleaned: List[str] = []
    seen = set()
    for raw in epcs_in:
        epc = normalize_epc(str(raw))
        if not epc:
            return False, f"bad_epc: {raw}", {}
        if epc in seen:
            continue
        seen.add(epc)
        cleaned.append(epc)

    if not cleaned:
        return False, "Scan at least 1 EPC", {}

    # STRICT: match total bags
    try:
        tb = int(total_bags)
    except:
        tb = 0
    if tb > 0 and len(cleaned) != tb:
        return False, f"Scan exactly {tb} EPC(s). Currently: {len(cleaned)}", {}

    # Optional: check duplicates already on chain for this crop
    existing = set(get_rfid_epcs_by_crop(crop_id) or [])
    for epc in cleaned:
        if epc in existing:
            return False, f"epc_already_registered: {epc}", {}

    # Send tx per EPC (since contract stores per EPC)
    tx_hashes = []
    for epc in cleaned:
        txh = register_rfids_onchain(
            user_id=user_id,
            username=username,
            crop_type=crop_type,
            crop_id=crop_id,
            packaging_date=packaging_date,
            expiry_date=expiry_date,
            bag_capacity=bag_capacity,
            total_bags=str(tb if tb else len(cleaned)),
            rfid_epc=epc
        )
        tx_hashes.append(txh)

    return True, "RFID registered on blockchain", {
        "cropId": crop_id,
        "count": len(cleaned),
        "txHashes": tx_hashes
    }

def fetch_rfid_list(crop_id: str) -> List[str]:
    return get_rfid_epcs_by_crop(crop_id) or []

def fetch_rfid_details(crop_id: str, epc: str):
    return get_rfid_record(crop_id, epc)
