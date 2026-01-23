# blockchain_setup.py — Unified exports for Polygon Amoy testnet

import json, re
from web3 import Web3

# Middleware import (supports both web3>=6.11 and older)
try:
    from web3.middleware import ExtraDataToPOAMiddleware as _POA
except ImportError:
    from web3.middleware import geth_poa_middleware as _POA  # web3<6

# ---------- Network & Keys (EDIT THESE) ----------
AMOY_RPC = "https://rpc-amoy.polygon.technology"


# Your deployed contract on Amoy (from Remix "Deployed Contracts")
CONTRACT_ADDRESS = "0xA357c6C8478874F3b951B4EdD7bF922338A67a8E"

# Your private key (testing only)
RAW_PRIVATE_KEY = "0xf368c0960ff642b0e1bef52e9ae20ce90a690005b11025081050bd85b9f12b5d"

# (NEW) Recall registry address & ABI file
RECALL_ADDR = "0x888332F60954778ca8ff945C2f44F662E089fb8A"
RECALL_ABI_FILE = "RecallGuardSimpleABI.json"  # <-- make sure this filename matches your JSON

# ---------- Helpers ----------
def _normalize_pk(pk: str) -> str:
    pk = pk.strip().replace(" ", "").replace("\n", "").replace("\r", "")
    hexpart = pk[2:] if pk.lower().startswith("0x") else pk
    if not pk.lower().startswith("0x"):
        pk = "0x" + pk
    if len(hexpart) != 64:
        raise ValueError(f"Private key must be 64 hex chars; got {len(hexpart)}")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", hexpart):
        raise ValueError("Private key contains non-hex characters")
    bytes.fromhex(hexpart)  # sanity
    return pk

def suggest_fees(multiplier: float = 1.25, min_prio_gwei: int = 25):
    """Return (priority_tip_wei, max_fee_wei) using fee_history."""
    hist = web3.eth.fee_history(5, "latest", [10, 50, 90])
    base = hist.get("baseFeePerGas", [0])[-1] or web3.to_wei(30, "gwei")
    tips = [r[-1] for r in hist.get("reward", []) if r]
    prio = max(tips) if tips else web3.to_wei(min_prio_gwei, "gwei")
    max_fee = int(base * multiplier + prio)
    return prio, max_fee

# ---------- Web3 Setup ----------
web3 = Web3(Web3.HTTPProvider(AMOY_RPC, request_kwargs={"timeout": 30}))
web3.middleware_onion.inject(_POA, layer=0)

account = web3.eth.account.from_key(_normalize_pk(RAW_PRIVATE_KEY))

# ---------- Traceability Contract ----------
with open("CropTraceabilityABI.json", "r") as f:
    trace_abi = json.load(f)
_TRACE_ADDR_CS = Web3.to_checksum_address(CONTRACT_ADDRESS)
contract = web3.eth.contract(address=_TRACE_ADDR_CS, abi=trace_abi)
contract_address = CONTRACT_ADDRESS  # legacy alias

# ---------- Recall Contract ----------
with open(RECALL_ABI_FILE, "r") as f:
    recall_abi = json.load(f)
_RECALL_ADDR_CS = Web3.to_checksum_address(RECALL_ADDR)
recall_contract = web3.eth.contract(address=_RECALL_ADDR_CS, abi=recall_abi)

def file_recall_onchain(crop_id: str, batch_code: str, severity: int, expires_at: int, reason_uri: str) -> str:
    """Convenience helper to file a recall on-chain via RecallGuardSimple."""
    fn = recall_contract.functions.fileRecall(crop_id, batch_code, severity, expires_at, reason_uri)
    gas = fn.estimate_gas({'from': account.address})
    prio, maxfee = suggest_fees()
    tx = fn.build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address, "pending"),


        'gas': int(gas * 1.2),
        'maxPriorityFeePerGas': prio,
        'maxFeePerGas': maxfee,
    })
    signed = account.sign_transaction(tx)
    txh = web3.eth.send_raw_transaction(signed.rawTransaction)
    return txh.hex()

# (Optional) sanity prints
try:
    if web3.is_connected() and web3.eth.chain_id != 80002:
        print(f"[WARN] Connected chainId={web3.eth.chain_id}, expected 80002 (Amoy).")
    if len(web3.eth.get_code(_TRACE_ADDR_CS)) <= 2:
        print(f"[WARN] No bytecode at {CONTRACT_ADDRESS} (trace) on Amoy.")
    if len(web3.eth.get_code(_RECALL_ADDR_CS)) <= 2:
        print(f"[WARN] No bytecode at {RECALL_ADDR} (recall) on Amoy.")
except Exception:
    pass

# ---------- Explicit exports ----------
__all__ = [
    "web3",
    "account",
    "contract", "CONTRACT_ADDRESS", "contract_address",
    "recall_contract", "RECALL_ADDR",
    "suggest_fees",
    "file_recall_onchain",
]
