# backend/blockchain.py
"""
Thin wrapper around blockchain_setup.py so services/routes can use
simple helper functions without touching Web3 directly.

Also exposes init_blockchain(app) used by app.py to attach web3 + contracts
to the Flask app config.
"""

from typing import Any

from __future__ import annotations

import os
import time
from typing import Optional
from blockchain_setup import (
    web3,
    account,
    contract,
    recall_contract,
    suggest_fees,
    file_recall_onchain,
)
from blockchain_setup import web3 as _web3  # reuse same instance
from blockchain_setup import account as _account
from blockchain_setup import contract as _contract

# --------------------------------------
#  App wiring (used by app.create_app)
# --------------------------------------
def init_blockchain(app: Any) -> None:
    """
    Wire blockchain_setup objects into Flask app.config
    and print a small status banner.

    Called from app.py:
        from backend.blockchain import init_blockchain
        init_blockchain(app)
    """
    print("⧉ Initializing Blockchain (using blockchain_setup.py)…")

    # Attach to app.config for easy access anywhere:
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

    print("✓ Blockchain wired from blockchain_setup.py")
    print(f"  • Account: {account.address}")
    print(f"  • Trace contract: {app.config['TRACE_CONTRACT_ADDRESS']}")
    print(f"  • Recall contract: {app.config['RECALL_CONTRACT_ADDRESS']}")


# --------------------------------------
# Traceability Helpers (used by services)
# --------------------------------------
def get_crop(crop_id: str):
    """
    Read crop details from the smart contract.
    """
    try:
        return contract.functions.getCrop(crop_id).call()
    except Exception as e:
        print("❌ get_crop() failed:", e)
        return None


def get_crop_history(crop_id: str):
    """
    Returns full crop lifecycle from chain.
    """
    try:
        return contract.functions.getCropHistory(crop_id).call()
    except Exception as e:
        print("❌ get_crop_history() failed:", e)
        return []


def get_user_crops(user_id: str):
    """
    Returns list of crop IDs owned by a user.
    """
    try:
        return contract.functions.getUserCrops(user_id).call()
    except Exception as e:
        print("❌ get_user_crops() failed:", e)
        return []


# --------------------------------------
# Recall Helpers (used by farmer + mfg)
# --------------------------------------
def file_recall(crop_id, batch_code, severity, expires_at, reason_uri):
    """
    Files a recall on-chain using blockchain_setup helper.
    """
    return file_recall_onchain(
        crop_id=crop_id,
        batch_code=batch_code,
        severity=severity,
        expires_at=expires_at,
        reason_uri=reason_uri,
    )

# --------------------------------------
#  Internal helper: get raw tx bytes
# --------------------------------------
def _raw_tx_bytes(signed) -> bytes:
    """
    Handle both eth-account styles:

    - signed.rawTransaction
    - signed.raw_transaction
    - or dict-style {"rawTransaction": ...}
    """
    # Object-style attributes
    raw = getattr(signed, "rawTransaction", None)
    if raw is None:
        raw = getattr(signed, "raw_transaction", None)

    # Dict-style (some eth-account versions)
    if raw is None and isinstance(signed, dict):
        raw = signed.get("rawTransaction") or signed.get("raw_transaction")

    if raw is None:
        raise TypeError("SignedTransaction has no raw tx bytes")

    return raw


# --------------------------------------
#  Crop Registration Helper
# --------------------------------------
def register_crop_onchain(
    user_id: str,
    crop_id: str,
    crop_type: str,
    crop_name:str,
    farmer_name: str,
    date_planted: str,
    farming_type: str | None,
    seed_type: str | None,
    location: str,
    area_size: float | int | str,
) -> str:
    """
    Call Solidity:
        function registerCrop(
            string userId,
            string cropId,
            string cropType,
            string farmerName,
            string datePlanted,
            string farmingType,
            string seedType,
            string location,
            uint256 areaSize
        )
    Returns tx hash (hex string).
    """
    from blockchain_setup import web3 as _web3  # reuse same instance
    from blockchain_setup import account as _account
    from blockchain_setup import contract as _contract

    # normalize areaSize → uint256 (store 2 decimals: 2.55 -> 255)
    try:
        area_f = float(area_size or 0)
        area_uint = int(round(area_f * 100))
    except Exception:
        area_uint = 0

    farming_type = farming_type or ""
    seed_type = seed_type or ""

    fn = _contract.functions.registerCrop(
        user_id,
        crop_id,
        crop_type,
        crop_name,
        farmer_name,
        date_planted,
        farming_type,
        seed_type,
        location,
        area_uint,
    )

    gas_est = fn.estimate_gas({"from": _account.address})
    prio, max_fee = suggest_fees()

    tx = fn.build_transaction(
        {
            "from": _account.address,
            "nonce": _web3.eth.get_transaction_count(
                _account.address, "pending"
            ),
            "chainId": 80002,  # Polygon Amoy
            "gas": int(gas_est * 1.20),
            "maxPriorityFeePerGas": prio,
            "maxFeePerGas": max_fee,
        }
    )

    signed = _account.sign_transaction(tx)

    # 🔥 Use helper that supports all eth-account variants
    raw_tx = _raw_tx_bytes(signed)

    tx_hash = _web3.eth.send_raw_transaction(raw_tx)
    return tx_hash.hex()





# --------------------------------------
#  Crop Registration Helper
# --------------------------------------

import json
from typing import Any
import json

def register_harvest_onchain(
    user_id: str,
    crop_id: str,
    harvester_name: str,
    harvest_date: str,
    harvest_quantity,
    packaging_type: str | None,
) -> str:
    from blockchain_setup import web3 as _web3
    from blockchain_setup import account as _account
    from blockchain_setup import contract as _contract

    # Normalize
    packaging_type = packaging_type or ""
    try:
        qty = float(harvest_quantity or 0)
    except:
        qty = 0.0

    fn = _contract.functions.registerHarvest(
        user_id,
        crop_id,
        harvester_name,
        harvest_date,
        int(qty),             # if contract expects uint
        packaging_type,

    )

    gas_est = fn.estimate_gas({"from": _account.address})
    prio, max_fee = suggest_fees()

    tx = fn.build_transaction(
        {
            "from": _account.address,
            "nonce": _web3.eth.get_transaction_count(_account.address, "pending"),
            "chainId": 80002,
            "gas": int(gas_est * 1.20),
            "maxPriorityFeePerGas": prio,
            "maxFeePerGas": max_fee,
        }
    )

    signed = _account.sign_transaction(tx)
    raw_tx = _raw_tx_bytes(signed)
    tx_hash = _web3.eth.send_raw_transaction(raw_tx)
    return tx_hash.hex()


def register_rfid_onchain(
        user_id: str,
        username:str,
        crop_type:str,
        crop_id: str,
        packaging_date:str,
        expiry_date:str,
        bag_capacity:str,
        total_bags:str,
        rfid_epc:str,

) -> str:
    from blockchain_setup import web3 as _web3
    from blockchain_setup import account as _account
    from blockchain_setup import contract as _contract
    from blockchain_setup import suggest_fees as _suggest_fees

    fn = _contract.functions.registerRFID(
        user_id,
        username,
        crop_type,
        crop_id,
        packaging_date,
        expiry_date,
        bag_capacity,
        total_bags,
        rfid_epc,
    )

    gas_est = fn.estimate_gas({"from":_account.address})
    prio, max_fee = _suggest_fees()

    tx = fn.build_transaction(
        {
            "from": _account.address,
            "nonce": _web3.eth.get_transaction_count(_account.address, "pending"),
            "chainId":80002,
            "gas": int(gas_est * 1.20),
            "maxPriorityFeePerGas":prio,
            "maxFeePerGas":max_fee,
        }
    )
    signed = _account.sign_transaction(tx)
    raw_tx = _raw_tx_bytes(signed)
    tx_hash = _web3.eth.send_raw_transaction(raw_tx)
    return tx_hash.hex()

    
def get_rfid_epcs_by_crop(crop_id: str):
    try:
        return contract.functions.getRFIDEpcsByCrop(crop_id).call()
    except Exception as e:
        print("❌ get_rfid_epcs_by_crop() failed:", e)
        return []
def get_rfid_record(crop_id: str, rfid_epc: str):
    try:
        return contract.functions.getRFID(crop_id, rfid_epc).call()
    except Exception as e:
        print("❌ get_rfid_record() failed:", e)
        return None
# --------------------------
# Explicit exports
# --------------------------------------
__all__ = [
    "init_blockchain",
    "web3",
    "account",
    "contract",
    "recall_contract",
    "get_crop",
    "get_crop_history",
    "get_user_crops",
    "suggest_fees",
    "file_recall",
    "register_crop_onchain",
    "register_harvest_onchain",
    "register_rfid_onchain",
    "get_rfid_epcs_by_crop",
    "get_rfid_record",
]



# ✅ IMPORT / SETUP from your existing blockchain.py
# You already have: web3, contract, account, suggest_fees, _raw_tx_bytes etc.
# Keep them as-is, just add the functions below.

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


def anchor_user_id_onchain(user_id: str) -> dict:
    """
    Anchors userId on-chain using registerUserId(userId).
    Returns: {"ok": True, "tx_hash": "..."} or {"ok": False, "error": "..."}
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
