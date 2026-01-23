# backend/recall.py
from flask import Blueprint, jsonify, request, session, current_app
from datetime import datetime
import time, json, os, re
from eth_utils import to_checksum_address
from web3.exceptions import ContractLogicError
from blockchain_setup import web3, account, contract as trace, suggest_fees

bp = Blueprint("recall_bp", __name__, url_prefix="/api/recall")

# ----------------------------
# Utils
# ----------------------------
def _raw_tx_bytes(signed):
    return getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction", None)

def _load_recall_abi():
    here = os.path.dirname(__file__)
    candidates = [
        os.path.join(os.getcwd(), "RecallGuardSimpleABI.json"),
        os.path.join(here, "..", "RecallGuardSimpleABI.json"),
        os.path.join(here, "RecallGuardSimpleABI.json"),
    ]
    for p in candidates:
        p = os.path.abspath(p)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    raise RuntimeError("RecallGuardSimpleABI.json not found. Put it in project root (beside app.py).")

RECALL_MIN_ABI = _load_recall_abi()

def _recall_contract():
    addr = current_app.config.get("RECALL_REGISTRY_ADDRESS")
    if not addr:
        raise RuntimeError("RECALL_REGISTRY_ADDRESS not configured in app.config")
    return web3.eth.contract(address=to_checksum_address(addr), abi=RECALL_MIN_ABI)

# ----------------------------
# EPC helpers (mirror others)
# ----------------------------
EPC_EXPECTED_HEX_LEN = int(os.environ.get("RFID_EPC_HEX_LEN", "24"))

def _epc_norm(s: str) -> str:
    if not s: return ""
    s = re.sub(r"[^0-9a-fA-F]", "", s).upper()
    return s[:EPC_EXPECTED_HEX_LEN] if EPC_EXPECTED_HEX_LEN else s

def _ensure_farmer_indexes(mongo):
    try:
        mongo.db.farmer_request.create_index([("rfidEpcs.epc", 1)])
        mongo.db.farmer_request.create_index([("rfidEpc", 1)])
        mongo.db.farmer_request.create_index([("cropId", 1)])
        mongo.db.farmer_request.create_index([("updated_at", -1), ("created_at", -1)])
    except Exception as e:
        current_app.logger.warning("index error: %s", e)

def _find_harvest_by_epc(mongo, epc_hex: str):
    q = {"$or": [{"rfidEpcs.epc": epc_hex}, {"rfidEpc": epc_hex}]}
    doc = mongo.db.farmer_request.find_one(q, sort=[("updated_at", -1), ("created_at", -1), ("_id", -1)])
    if not doc:
        return None, None
    matched = None
    bags = doc.get("rfidEpcs") if isinstance(doc.get("rfidEpcs"), list) else []
    for b in bags or []:
        try:
            if (b.get("epc") or "").upper() == epc_hex:
                matched = b
                break
        except Exception:
            pass
    return doc, matched

def _expected_bags_from_doc(doc) -> int:
    if not doc: return 0
    if doc.get("bagQty"):
        try: return int(doc["bagQty"])
        except Exception: pass
    arr = doc.get("rfidEpcs") if isinstance(doc.get("rfidEpcs"), list) else []
    try:
        return len({(b.get("epc") or "").upper() for b in arr if b and b.get("epc")})
    except Exception:
        return len(arr or [])

# ============================================================
#                 Scan APIs
# ============================================================
@bp.post("/scan/init")
def recall_scan_init():
    from app import mongo
    data = request.get_json(silent=True) or {}
    crop_id = (data.get("cropId") or "").strip()
    if not crop_id:
        return jsonify({"ok": False, "err": "cropId required"}), 400

    _ensure_farmer_indexes(mongo)
    doc = mongo.db.farmer_request.find_one({"cropId": crop_id}, sort=[("updated_at", -1), ("created_at", -1), ("_id", -1)])
    if not doc:
        return jsonify({"ok": False, "err": "crop not found"}), 404

    expected = _expected_bags_from_doc(doc)
    session["recall_scan"] = {
        "cropId": crop_id,
        "expected": int(expected),
        "scanned": [],
        "startedAt": int(time.time()),
    }
    return jsonify({"ok": True, "expected": int(expected), "scanned": 0})

@bp.post("/scan/add")
def recall_scan_add():
    stash = session.get("recall_scan")
    if not stash or not stash.get("cropId"):
        return jsonify({"ok": False, "err": "scan not initialized"}), 400

    data = request.get_json(silent=True) or {}
    epc = _epc_norm(data.get("epc") or "")
    if not epc or len(epc) < EPC_EXPECTED_HEX_LEN:
        return jsonify({"ok": False, "err": "bad_or_short_epc"}), 400

    time.sleep(5)
    scanned = list(stash.get("scanned") or [])
    if epc not in scanned:
        scanned.append(epc)

    stash["scanned"] = scanned
    session["recall_scan"] = stash
    expected = int(stash.get("expected") or 0)
    count = len(scanned)
    mismatch = (expected != 0) and (count != expected)

    return jsonify({
        "ok": True,
        "cropId": stash.get("cropId"),
        "expected": expected,
        "scanned": count,
        "epcs": scanned,
        "mismatch": mismatch
    })

@bp.get("/scan/status")
def recall_scan_status():
    stash = session.get("recall_scan") or {}
    return jsonify({
        "ok": True,
        "cropId": stash.get("cropId"),
        "expected": int(stash.get("expected") or 0),
        "scanned": len(stash.get("scanned") or []),
        "epcs": list(stash.get("scanned") or []),
        "startedAt": stash.get("startedAt")
    })

@bp.post("/scan/reset")
def recall_scan_reset():
    session.pop("recall_scan", None)
    return jsonify({"ok": True})

@bp.post("/write")
def recall_write_mapping():
    if not session.get("user_id"):
        return jsonify({"ok": False, "err": "unauthorized"}), 401
    from app import mongo

    data = request.get_json(silent=True) or {}
    epc = _epc_norm(data.get("epc") or "")
    payload = data.get("payload") or {}
    if not epc or len(epc) < EPC_EXPECTED_HEX_LEN:
        return jsonify({"ok": False, "err": "bad_or_short_epc"}), 400

    mongo.db.rfid_maps.update_one(
        {"epc": epc},
        {"$set": {"epc": epc, "payload": payload, "updated_at": datetime.utcnow()}},
        upsert=True
    )
    return jsonify({"ok": True})

@bp.get("/resolve")
def recall_resolve_epc():
    if not session.get("user_id"):
        return jsonify({"ok": False, "err": "unauthorized"}), 401
    from app import mongo

    _ensure_farmer_indexes(mongo)
    epc = _epc_norm(request.args.get("epc") or "")
    if not epc or len(epc) < EPC_EXPECTED_HEX_LEN:
        return jsonify({"ok": False, "err": "bad_or_short_epc"}), 400

    doc, matched = _find_harvest_by_epc(mongo, epc)
    if not doc:
        return jsonify({"ok": False, "err": "unknown_epc"}), 404

    arr = doc.get("rfidEpcs") if isinstance(doc.get("rfidEpcs"), list) else []
    bag_list, total_units = [], 0
    for b in arr or []:
        try:
            e = (b.get("epc") or "").upper()
            q = int(b.get("bagQty") or 0)
            bag_list.append({"epc": e, "bagQty": q, "added_at": b.get("added_at")})
            total_units += q
        except Exception:
            pass

    payload = {
        "cropId":          doc.get("cropId") or "",
        "cropType":        doc.get("cropType") or "",
        "harvestQuantity": doc.get("harvestQuantity") or 0,
        "packagingType":   doc.get("packagingType") or "",
        "farmerId":        doc.get("farmerId") or "",
        "manufacturerId":  doc.get("manufacturerId") or "",
        "status":          doc.get("status") or "Pending",
        "updated_at":      doc.get("updated_at") or doc.get("created_at")
    }
    expected = _expected_bags_from_doc(doc)
    matched_bag = None
    if matched:
        matched_bag = {
            "epc": (matched.get("epc") or "").upper(),
            "bagQty": int(matched.get("bagQty") or 0),
            "added_at": matched.get("added_at")
        }

    return jsonify({
        "ok": True,
        "tag": payload,
        "bagCount": int(expected),
        "totalUnits": int(total_units),
        "bagEpcs": bag_list,
        "matchedBag": matched_bag
    })

# ---------- Linked parties ----------
@bp.get("/linked-parties")
def linked_parties():
    crop_id = (request.args.get("crop_id") or "").strip()
    scope   = (request.args.get("scope") or "auto").lower()
    if not crop_id:
        return jsonify({"ok": False, "err": "crop_id required"}), 400
    try:
        history = trace.functions.getCropHistory(crop_id).call()
        participants, seen = [], set()

        def _role_from_status(status: str) -> str:
            s = (status or "").lower()
            if s.startswith("plant"): return "Farmer"
            if s.startswith("process"): return "Manufacturer"
            if s.startswith("distrib"): return "Distributor"
            if s.startswith("transp"): return "Transporter"
            if s.startswith("sold"): return "Retailer"
            return "Participant"

        for ev in history:
            status = ev[0]
            role   = _role_from_status(status)
            userId = ev[12]
            actor  = ev[2]
            office = ev[6] if len(ev) > 6 else ""
            if not userId:
                continue
            key = (role, userId)
            if key in seen:
                continue
            seen.add(key)
            participants.append({"role": role, "userId": userId, "name": actor, "officeAddress": office})

        role_order = ["Farmer","Manufacturer","Distributor","Transporter","Retailer"]
        by_role = {r: [] for r in role_order}
        for p in participants:
            by_role.get(p["role"], []).append(p)

        if scope == "upstream":
            filt = by_role["Farmer"] + by_role["Manufacturer"]
        elif scope == "downstream":
            filt = by_role["Transporter"] + by_role["Retailer"] + by_role["Distributor"]
        else:
            filt = []
            for r in role_order:
                filt.extend(by_role[r])

        return jsonify({"ok": True, "participants": filt})
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500

# ============================================================
#                    Recall filing (UPDATED)
# ============================================================
def _has_fn(c, name):
    try:
        getattr(c.functions, name)
        return True
    except AttributeError:
        return False

def _get_fn_abi(c, name):
    fn = getattr(c.functions, name, None)
    if fn is None: return None, None
    for item in c.abi:
        if item.get("type") == "function" and item.get("name") == name:
            return fn, item
    return fn, None

def _tuple_components(fn_abi, index=0):
    """Return list of components for the N-th input if it's a tuple; else None."""
    if not fn_abi: return None
    inputs = fn_abi.get("inputs") or []
    if index >= len(inputs): return None
    arg = inputs[index]
    if arg.get("type") == "tuple":
        return arg.get("components") or []
    return None

def _build_tuple_from_components(components, values_by_name, positional_fallback):
    if not components:
        return tuple(positional_fallback)
    out = []
    for i, comp in enumerate(components):
        nm = comp.get("name") or ""
        typ = comp.get("type") or ""
        if nm in values_by_name:
            out.append(values_by_name[nm])
        else:
            if i < len(positional_fallback):
                out.append(positional_fallback[i])
            else:
                if typ.endswith("[]"):
                    out.append([])
                elif typ.startswith("uint") or typ.startswith("int"):
                    out.append(0)
                else:
                    out.append("")
    return tuple(out)

def _decode_revert_reason(c, fn):
    try:
        call_data = fn._encode_transaction_data()
        to = c.address
        web3.eth.call({"to": to, "data": call_data}, web3.eth.block_number)
        return None
    except ContractLogicError as e:
        return str(e)
    except Exception as e:
        return str(e)

def _owner_must_match(c):
    try:
        owner = c.functions.owner().call()
        return owner.lower() == account.address.lower(), owner
    except Exception:
        return True, None

@bp.post("/report")
def report_recall():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "err": "unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    crop_id     = (data.get("cropId") or "").strip()
    batch_code  = (data.get("batchCode") or "").strip()
    severity_in = (data.get("severity") or "").lower()
    description = data.get("description") or ""
    evidenceUrl = data.get("evidenceUrl") or ""
    dateTo      = (data.get("dateTo") or "").strip()

    crop_type   = (data.get("cropType") or "").strip()
    location    = (data.get("location") or "").strip()
    contamin    = (data.get("riskType") or "").strip()

    rec_scope   = (data.get("recipientScope") or "auto").lower()
    custom_recs = data.get("customRecipients") or []
    recipients  = [(r.get("userId") or "").strip() for r in custom_recs if (r.get("userId") or "").strip()]

    if not crop_id:
        return jsonify({"ok": False, "err": "cropId required"}), 400
    sev_map = {"low":0, "medium":1, "high":2, "critical":3}
    if severity_in not in sev_map:
        return jsonify({"ok": False, "err": "invalid severity"}), 400
    severity = int(sev_map[severity_in])

    expiresAt = 0
    if dateTo:
        try:
            expiresAt = int(time.mktime(datetime.strptime(dateTo, "%Y-%m-%d").timetuple()))
        except Exception:
            expiresAt = 0

    # Server-side resolve recipients if none and scope != custom
    roles_code_map = {"Farmer":1,"Manufacturer":2,"Distributor":3,"Transporter":4,"Retailer":5}
    if not recipients and rec_scope != "custom":
        try:
            history = trace.functions.getCropHistory(crop_id).call()
            def _role_from_status(status: str) -> str:
                s = (status or "").lower()
                if s.startswith("plant"): return "Farmer"
                if s.startswith("process"): return "Manufacturer"
                if s.startswith("distrib"): return "Distributor"
                if s.startswith("transp"): return "Transporter"
                if s.startswith("sold"): return "Retailer"
                return "Participant"
            temp = [{"role": _role_from_status(ev[0]), "userId": ev[12] or ""} for ev in history if (ev[12] or "")]
            if rec_scope == "upstream":
                keep = {"Farmer","Manufacturer"}
                recipients = [t["userId"] for t in temp if t["role"] in keep]
            elif rec_scope == "downstream":
                keep = {"Distributor","Transporter","Retailer"}
                recipients = [t["userId"] for t in temp if t["role"] in keep]
            else:
                role_order = ["Farmer","Manufacturer","Distributor","Transporter","Retailer"]
                ordered = []
                for r in role_order:
                    ordered.extend([t["userId"] for t in temp if t["role"] == r])
                recipients = ordered
            # produce roles aligned to recipients
            role_by_uid = {}
            for t in temp:
                if t["userId"]:
                    role_by_uid[t["userId"]] = roles_code_map.get(t["role"], 0)
            linked_roles = [int(role_by_uid.get(u, 0)) for u in recipients]
        except Exception:
            linked_roles = [0 for _ in recipients]
    else:
        # FE might have sent explicit roles; if not, default zeros with same length
        maybe_roles = data.get("linkedRoles") or []
        if len(maybe_roles) == len(recipients):
            linked_roles = [int(x) & 0xFF for x in maybe_roles]
        else:
            linked_roles = [0 for _ in recipients]

    # Build reasonURI
    if evidenceUrl:
        reasonURI = evidenceUrl
    else:
        embed = {
            "t": "recall",
            "desc": (description or "")[:380],
            "ev": evidenceUrl,
            "contamination": contamin,
            "location": location
        }
        if recipients:
            embed["recipients"] = recipients
        reasonURI = "data:application/json," + json.dumps(embed, separators=(",",":"))

    c = _recall_contract()

    # Owner preflight
    is_owner, owner_addr = _owner_must_match(c)
    if not is_owner:
        return jsonify({
            "ok": False,
            "err": "not owner (contract requires onlyOwner)",
            "expectedOwner": owner_addr,
            "usingFrom": account.address
        }), 403

    # Function availability
    has_full   = _has_fn(c, "fileRecallFull")
    has_recall = _has_fn(c, "fileRecall")
    has_parts  = _has_fn(c, "fileParticipants")

    fn_full, abi_full   = _get_fn_abi(c, "fileRecallFull") if has_full else (None, None)
    fn_recall, abi_rec  = _get_fn_abi(c, "fileRecall")     if has_recall else (None, None)
    fn_parts, abi_parts = _get_fn_abi(c, "fileParticipants") if has_parts else (None, None)

    # Components (a = input 0, p = input 1 for fileRecallFull)
    comp_a = _tuple_components(abi_rec, 0) or _tuple_components(abi_full, 0)
    comp_p = _tuple_components(abi_parts, 0) or _tuple_components(abi_full, 1)

    # ---- build tuples ----
    # a: (cropId, batchCode, severity, expiresAt, reasonURI, contaminationType, location)
    a_by_name = {
        "cropId": crop_id,
        "batchCode": batch_code,
        "severity": int(severity),
        "expiresAt": int(expiresAt),
        "reasonURI": reasonURI,
        "contaminationType": contamin,
        "location": location
    }
    a_positional = (
        crop_id,
        batch_code,
        int(severity),
        int(expiresAt),
        reasonURI,
        contamin,
        location
    )
    a_tuple = _build_tuple_from_components(comp_a or [], a_by_name, a_positional)

    # p: (requesterUserId, cropType, cropId, batchCode, recipients, roles)
    p_by_name = {
        "requesterUserId": str(user_id),
        "cropType": crop_type,
        "cropId": crop_id,
        "batchCode": batch_code,
        "recipients": recipients,
        "roles": [int(x) & 0xFF for x in linked_roles]
    }
    p_positional = (
        str(user_id),
        crop_type,
        crop_id,
        batch_code,
        recipients,
        [int(x) & 0xFF for x in linked_roles]
    )
    p_tuple = _build_tuple_from_components(comp_p or [], p_by_name, p_positional)

    def _send(fn):
        reason = _decode_revert_reason(c, fn)
        if isinstance(reason, str) and "revert" in reason.lower():
            raise RuntimeError(f"preflight_revert: {reason}")
        gas_est = fn.estimate_gas({'from': account.address})
        prio, max_fee = suggest_fees()
        txn = fn.build_transaction({
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address, "pending"),
            'chainId': web3.eth.chain_id,
            'gas': int(gas_est * 1.20),
            'maxPriorityFeePerGas': prio,
            'maxFeePerGas': max_fee,
        })
        signed = account.sign_transaction(txn)
        raw = _raw_tx_bytes(signed)
        if raw is None:
            raise RuntimeError("raw_tx_bytes_missing")
        txh = web3.eth.send_raw_transaction(raw)
        rcpt = web3.eth.wait_for_transaction_receipt(txh, timeout=180)
        if not rcpt or rcpt.status != 1:
            raise RuntimeError("tx_failed_or_reverted")
        return txh.hex()

    tx_hash = None
    parts_tx = None

    try:
        if has_full and comp_a and comp_p:
            # fileRecallFull(a, p)
            fn = c.functions.fileRecallFull(a_tuple, p_tuple)
            tx_hash = _send(fn)
        elif has_recall:
            # fileRecall(a) (tuple) or legacy flat
            if comp_a:
                fn = c.functions.fileRecall(a_tuple)
            else:
                fn = c.functions.fileRecall(crop_id, batch_code, int(severity), int(expiresAt), reasonURI)
            tx_hash = _send(fn)

            if has_parts:
                # fileParticipants(p) (tuple) or legacy flat
                if comp_p:
                    fnp = c.functions.fileParticipants(p_tuple)
                else:
                    fnp = c.functions.fileParticipants(
                        str(user_id), crop_type, crop_id, batch_code, recipients, [int(x) & 0xFF for x in linked_roles]
                    )
                parts_tx = _send(fnp)
        else:
            return jsonify({"ok": False, "err": "No supported recall methods found in ABI"}), 500

    except Exception as e:
        try:
            bal = web3.eth.get_balance(account.address)
        except Exception:
            bal = None
        return jsonify({
            "ok": False,
            "err": str(e),
            "chainId": web3.eth.chain_id,
            "from": account.address,
            "balanceWei": bal,
            "recallAddr": current_app.config.get("RECALL_REGISTRY_ADDRESS"),
            "debug": {
                "has_full": has_full, "has_recall": has_recall, "has_parts": has_parts,
                "a_tuple": a_tuple, "p_tuple": p_tuple
            }
        }), 500

    return jsonify({
        "ok": True,
        "txHash": tx_hash,
        "participantsTx": parts_tx,
        "chainId": web3.eth.chain_id,
        "recipients": recipients
    })
