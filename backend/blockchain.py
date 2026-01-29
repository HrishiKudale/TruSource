# backend/blockchain.py
"""
Thin wrapper around blockchain_setup.py so services/routes can use
simple helper functions without touching Web3 directly.

Also exposes init_blockchain(app) used by app.py to attach web3 + contracts
to the Flask app config.

✅ IMPORTANT FIXES INCLUDED:
- `from __future__ import annotations` is placed correctly (top of file).
- Removed duplicate / late imports (no imports in the middle of the file).
- Removed duplicate `import json` and repeated `typing` imports.
- No circular/self imports.
- All helper functions kept and cleaned.
- Added missing return typing and safer conversions.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Union

# NOTE:
# If this file is inside "backend/", and blockchain_setup.py is ALSO inside "backend/",
# then prefer: `from backend.blockchain_setup import ...`
# If blockchain_setup.py is at repo root, keep: `from blockchain_setup import ...`
# Based on your current file, you are using `from blockchain_setup import ...`
from blockchain_setup import (
    web3,
    account,
    contract,
    recall_contract,
    suggest_fees,
    file_recall_onchain,
)

# -------------------------------------------------------------------
# App wiring (used by app.create_app)
# -------------------------------------------------------------------
def init_blockchain(app: Any) -> None:
    """
    Wire blockchain_setup objects into Flask app.config.

    Called from app.py:
        from backend.blockchain import init_blockchain
        init_blockchain(app)
    """
    print("⧉ Initializing Blockchain (using blockchain_setup.py)…")

    app.config["WEB3"] = web3
    app.config["BLOCKCHAIN_ACCOUNT"] = account
    app.config["TRACE_CONTRACT"] = contract
    app.config["RECALL_CONTRACT"] = recall_contract

    # Optional: also expose addresses
    try:
        app.config["TRACE_CONTRACT_ADDRESS"] = contract.address
    except Exception:
        app.config["TRACE_CONTRACT_ADDRESS"] = None

    try:
        app.config["RECALL_CONTRACT_ADDRESS"] = recall_contract.address
    except Exception:
        app.config["RECALL_CONTRACT_ADDRESS"] = None

    try:
        acct_addr = account.address
    except Exception:
        acct_addr = None

    print("✓ Blockchain wired from blockchain_setup.py")
    print(f"  • Account: {acct_addr}")
    print(f"  • Trace contract: {app.config['TRACE_CONTRACT_ADDRESS']}")
    print(f"  • Recall contract: {app.config['RECALL_CONTRACT_ADDRESS']}")


# -------------------------------------------------------------------
# Traceability Read Helpers (used by services)
# -------------------------------------------------------------------
def get_crop(crop_id: str):
    """Read crop details from the smart contract."""
    try:
        return contract.functions.getCrop(crop_id).call()
    except Exception as e:
        print("❌ get_crop() failed:", e)
        return None


def get_crop_history(crop_id: str):
    """Returns full crop lifecycle from chain."""
    try:
        return contract.functions.getCropHistory(crop_id).call()
    except Exception as e:
        print("❌ get_crop_history() failed:", e)
        return []


def get_user_crops(user_id: str):
    """Returns list of crop IDs owned by a user."""
    try:
        return contract.functions.getUserCrops(user_id).call()
    except Exception as e:
        print("❌ get_user_crops() failed:", e)
        return []


# -------------------------------------------------------------------
# Recall Helpers (used by farmer + mfg)
# -------------------------------------------------------------------
def file_recall(crop_id: str, batch_code: str, severity: str, expires_at: int, reason_uri: str):
    """Files a recall on-chain using blockchain_setup helper."""
    return file_recall_onchain(
        crop_id=crop_id,
        batch_code=batch_code,
        severity=severity,
        expires_at=expires_at,
        reason_uri=reason_uri,
    )


# -------------------------------------------------------------------
# Internal helper: get raw tx bytes (supports eth-account variants)
# -------------------------------------------------------------------
def _raw_tx_bytes(signed) -> bytes:
    """
    Handle both eth-account styles:
      - signed.rawTransaction
      - signed.raw_transaction
      - or dict-style {"rawTransaction": ...}
    """
    raw = getattr(signed, "rawTransaction", None)
    if raw is None:
        raw = getattr(signed, "raw_transaction", None)

    if raw is None and isinstance(signed, dict):
        raw = signed.get("rawTransaction") or signed.get("raw_transaction")

    if raw is None:
        raise TypeError("SignedTransaction has no raw tx bytes")

    return raw


# -------------------------------------------------------------------
# Crop Registration Helper (registerCrop)
# Solidity signature in your contract:
# registerCrop(userId, cropId, cropName, cropType, farmerName, datePlanted,
#              farmingType, seedType, location, areaSize)
# -------------------------------------------------------------------
def register_crop_onchain(
    user_id: str,
    crop_id: str,
    crop_type: str,
    crop_name: str,
    farmer_name: str,
    date_planted: str,
    farming_type: Optional[str],
    seed_type: Optional[str],
    location: str,
    area_size: Union[float, int, str],
) -> str:
    """
    Returns tx hash (hex string).
    """
    # normalize areaSize → uint256 (store 2 decimals: 2.55 -> 255)
    try:
        area_f = float(area_size or 0)
        area_uint = int(round(area_f * 100))
    except Exception:
        area_uint = 0

    farming_type = farming_type or ""
    seed_type = seed_type or ""

    fn = contract.functions.registerCrop(
        user_id,
        crop_id,
        crop_name,
        crop_type,
        farmer_name,
        date_planted,
        farming_type,
        seed_type,
        location,
        area_uint,
    )

    gas_est = fn.estimate_gas({"from": account.address})
    prio, max_fee = suggest_fees()

    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address, "pending"),
            "chainId": 80002,  # Polygon Amoy
            "gas": int(gas_est * 1.20),
            "maxPriorityFeePerGas": prio,
            "maxFeePerGas": max_fee,
        }
    )

    signed = account.sign_transaction(tx)
    raw_tx = _raw_tx_bytes(signed)
    tx_hash = web3.eth.send_raw_transaction(raw_tx)
    return tx_hash.hex()


# -------------------------------------------------------------------
# Harvest Registration Helper (registerHarvest)
# Solidity signature in your contract:
# registerHarvest(userId, cropId, harvestDate, harvesterName, harvestQuantity, packagingType)
# -------------------------------------------------------------------
def register_harvest_onchain(
    user_id: str,
    crop_id: str,
    harvest_date: str,
    harvester_name: str,
    harvest_quantity: Union[str, int, float],
    packaging_type: Optional[str],
) -> str:
    """
    Returns tx hash (hex string).
    """
    packaging_type = packaging_type or ""
    try:
        qty = float(harvest_quantity or 0)
    except Exception:
        qty = 0.0

    fn = contract.functions.registerHarvest(
        user_id,
        crop_id,
        harvest_date,
        harvester_name,
        int(qty),
        packaging_type,
    )

    gas_est = fn.estimate_gas({"from": account.address})
    prio, max_fee = suggest_fees()

    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address, "pending"),
            "chainId": 80002,
            "gas": int(gas_est * 1.20),
            "maxPriorityFeePerGas": prio,
            "maxFeePerGas": max_fee,
        }
    )

    signed = account.sign_transaction(tx)
    raw_tx = _raw_tx_bytes(signed)
    tx_hash = web3.eth.send_raw_transaction(raw_tx)
    return tx_hash.hex()


# -------------------------------------------------------------------
# RFID Registration
# Your Solidity currently shows registerRFIDs(...) (plural), NOT registerRFID(...)
# But your old python called registerRFID(...).
#
# ✅ This implementation keeps BOTH:
# - register_rfid_onchain_single() → calls registerRFID if present
# - register_rfids_onchain()       → calls registerRFIDs (recommended with your Solidity)
# -------------------------------------------------------------------
def register_rfid_onchain_single(
    user_id: str,
    username: str,
    crop_name: str,
    crop_type: str,
    crop_id: str,
    packaging_date: str,
    expiry_date: str,
    bag_capacity: str,
    total_bags: str,
    rfid_epc: str,
) -> str:
    """
    Calls contract.registerRFID(...) if that function exists in ABI.
    Returns tx hash.
    """
    fn = contract.functions.registerRFID(
        user_id,
        username,
        crop_name,
        crop_type,
        crop_id,
        packaging_date,
        expiry_date,
        bag_capacity,
        total_bags,
        rfid_epc,
    )

    gas_est = fn.estimate_gas({"from": account.address})
    prio, max_fee = suggest_fees()

    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address, "pending"),
            "chainId": 80002,
            "gas": int(gas_est * 1.20),
            "maxPriorityFeePerGas": prio,
            "maxFeePerGas": max_fee,
        }
    )
    signed = account.sign_transaction(tx)
    raw_tx = _raw_tx_bytes(signed)
    tx_hash = web3.eth.send_raw_transaction(raw_tx)
    return tx_hash.hex()


def register_rfids_onchain(
    user_id: str,
    username: str,
    crop_name: str,
    crop_type: str,
    crop_id: str,
    packaging_date: str,
    expiry_date: str,
    bag_capacity: str,
    total_bags: str,
    epcs: List[str],
) -> str:
    """
    Calls contract.registerRFIDs(...) (plural) which matches your Solidity.
    Returns tx hash.
    """
    fn = contract.functions.registerRFIDs(
        user_id,
        username,
        crop_name,
        crop_type,
        crop_id,
        packaging_date,
        expiry_date,
        bag_capacity,
        total_bags,
        epcs,
    )

    gas_est = fn.estimate_gas({"from": account.address})
    prio, max_fee = suggest_fees()

    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address, "pending"),
            "chainId": 80002,
            "gas": int(gas_est * 1.20),
            "maxPriorityFeePerGas": prio,
            "maxFeePerGas": max_fee,
        }
    )
    signed = account.sign_transaction(tx)
    raw_tx = _raw_tx_bytes(signed)
    tx_hash = web3.eth.send_raw_transaction(raw_tx)
    return tx_hash.hex()


def get_rfid_epcs_by_crop(crop_id: str):
    try:
        return contract.functions.getRFIDEpcsByCrop(crop_id).call()
    except Exception as e:
        print("❌ get_rfid_epcs_by_crop() failed:", e)
        return []


def get_rfid_record(crop_id: str, rfid_epc: str):
    """
    NOTE: Your Solidity shared does NOT include getRFID(cropId, epc).
    If your deployed ABI has getRFID, this will work.
    Otherwise you'll get an ABI error. Keep as-is if you already added getRFID in contract.
    """
    try:
        return contract.functions.getRFID(crop_id, rfid_epc).call()
    except Exception as e:
        print("❌ get_rfid_record() failed:", e)
        return None


# -------------------------------------------------------------------
# UserId generation + anchoring
# Only userId goes on chain via registerUserId(userId)
# -------------------------------------------------------------------
def generate_user_id(role: str) -> Optional[str]:
    prefix_map = {
        "farmer": "FRM",
        "manufacturer": "MFG",
        "distributor": "DIST",
        "retailer": "RET",
        "transporter": "TRN",
        "warehouse": "WRH",
        "warehousing": "WRH",
    }
    prefix = prefix_map.get((role or "").strip().lower())
    if not prefix:
        return None
    return f"{prefix}{os.urandom(3).hex().upper()}{int(time.time())}"


def should_anchor_user(role: str) -> bool:
    return (role or "").strip().lower() in {"farmer", "manufacturer", "distributor", "retailer"}


def anchor_user_id_onchain(user_id: str) -> Dict[str, Any]:
    """
    Anchors userId on-chain using registerUserId(userId).
    Returns:
      {"ok": True,  "tx_hash": "..."}
      {"ok": False, "error": "..."}
    """
    try:
        fn = contract.functions.registerUserId(user_id)

        gas_est = fn.estimate_gas({"from": account.address})
        prio, max_fee = suggest_fees()

        txn = fn.build_transaction(
            {
                "from": account.address,
                "nonce": web3.eth.get_transaction_count(account.address, "pending"),
                "chainId": 80002,  # Polygon Amoy
                "gas": int(gas_est * 1.20),
                "maxPriorityFeePerGas": prio,
                "maxFeePerGas": max_fee,
            }
        )

        signed = account.sign_transaction(txn)
        tx_hash = web3.eth.send_raw_transaction(_raw_tx_bytes(signed))
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

        if not receipt or receipt.status != 1:
            return {"ok": False, "error": "Blockchain transaction failed (receipt.status != 1)"}

        return {"ok": True, "tx_hash": web3.to_hex(tx_hash)}

    except Exception as e:
        return {"ok": False, "error": f"Blockchain error: {e}"}


# -------------------------------------------------------------------
# Explicit exports
# -------------------------------------------------------------------
__all__ = [
    "init_blockchain",
    "web3",
    "account",
    "contract",
    "recall_contract",
    "suggest_fees",
    "file_recall",
    "get_crop",
    "get_crop_history",
    "get_user_crops",
    "register_crop_onchain",
    "register_harvest_onchain",
    "register_rfid_onchain_single",
    "register_rfids_onchain",
    "get_rfid_epcs_by_crop",
    "get_rfid_record",
    "generate_user_id",
    "should_anchor_user",
    "anchor_user_id_onchain",
]
