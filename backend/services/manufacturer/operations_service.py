from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List

from backend.mongo_safe import get_col
from backend.models.manufacturer.operation_model import (
    OperationRegistrationModel,
    OperationInfoModel,
)

try:
    from backend.blockchain import (
        get_user_operations,
        get_operation_history,
        register_operation_onchain,
    )
except Exception:
    get_user_operations = None
    get_operation_history = None
    register_operation_onchain = None


class OperationService:

    @staticmethod
    def _num(value, default=0):
        try:
            if value in ("", None):
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _operation_ids_from_mongo(manufacturer_id: str) -> List[str]:
        col = get_col("manufacturer_operations")
        if col is None:
            return []

        docs = col.find(
            {
                "$or": [
                    {"manufacturer_id": manufacturer_id},
                    {"manufacturerId": manufacturer_id},
                ]
            },
            {"operationId": 1, "operation_id": 1},
        )

        ids = []
        seen = set()

        for doc in docs:
            oid = doc.get("operationId") or doc.get("operation_id")
            oid = str(oid or "").strip()

            if oid and oid not in seen:
                seen.add(oid)
                ids.append(oid)

        return ids

    @staticmethod
    def get_operation_ids(manufacturer_id: str) -> List[str]:
        try:
            if get_user_operations:
                ids = get_user_operations(manufacturer_id) or []
            else:
                ids = OperationService._operation_ids_from_mongo(manufacturer_id)
        except Exception as e:
            print(f"[OperationService.get_operation_ids] {e}")
            ids = OperationService._operation_ids_from_mongo(manufacturer_id)

        unique = []
        seen = set()

        for oid in ids:
            oid = str(oid or "").strip()
            if oid and oid not in seen:
                seen.add(oid)
                unique.append(oid)

        return unique

    @staticmethod
    def _history_from_mongo(operation_id: str):
        col = get_col("manufacturer_operations")
        if col is None:
            return []

        doc = col.find_one(
            {
                "$or": [
                    {"operationId": operation_id},
                    {"operation_id": operation_id},
                ]
            },
            sort=[("created_at", -1)],
        )

        return [doc] if doc else []

    @staticmethod
    def get_operation_history_safe(operation_id: str):
        try:
            if get_operation_history:
                return get_operation_history(operation_id) or []
        except Exception as e:
            print(f"[OperationService.get_operation_history_safe] blockchain error: {e}")

        return OperationService._history_from_mongo(operation_id)

    @staticmethod
    def get_my_operations(manufacturer_id: str) -> Dict[str, Any]:
        operation_ids = OperationService.get_operation_ids(manufacturer_id)

        products = []
        requested_products = 0
        active_operations = 0
        processed_operations = 0

        for operation_id in operation_ids:
            detail = OperationService.get_operation_detail(
                manufacturer_id=manufacturer_id,
                operation_id=operation_id,
            )

            status = (detail.get("status") or "").lower()

            if status in ("requested", "pending"):
                requested_products += 1

            if status in ("active", "processing", "in_progress"):
                active_operations += 1

            if status in ("processed", "completed", "manufactured"):
                processed_operations += 1

            products.append(
                {
                    "operation_id": detail.get("operationId"),
                    "crop_id": detail.get("cropId"),
                    "crop_name": detail.get("cropName"),
                    "sowing_date": detail.get("sowingDate"),
                    "harvest_date": detail.get("harvestDate"),
                    "total_qty": detail.get("totalQty", 0),
                    "status": detail.get("status") or "Requested",
                    "crop_type": detail.get("cropType") or "",
                    "buyer": detail.get("buyer") or "",
                }
            )

        return {
            "products": products,
            "total_products": len(products),
            "requested_products": requested_products,
            "active_operations": active_operations,
            "processed_operations": processed_operations,
        }

    @staticmethod
    def get_operation_detail(
        manufacturer_id: str,
        operation_id: str,
    ) -> Dict[str, Any]:

        history = OperationService.get_operation_history_safe(operation_id)

        operation = None

        for ev in history:
            if isinstance(ev, dict):
                operation = {
                    "operationId": ev.get("operationId") or ev.get("operation_id") or operation_id,
                    "manufacturerId": ev.get("manufacturerId") or ev.get("manufacturer_id") or manufacturer_id,

                    "cropId": ev.get("cropId") or ev.get("crop_id") or "",
                    "cropName": ev.get("cropName") or ev.get("crop_name") or "",
                    "cropType": ev.get("cropType") or ev.get("crop_type") or "",

                    "sowingDate": ev.get("sowingDate") or ev.get("sowing_date") or ev.get("datePlanted") or "",
                    "harvestDate": ev.get("harvestDate") or ev.get("harvest_date") or "",

                    "totalQty": OperationService._num(ev.get("totalQty") or ev.get("total_qty")),
                    "requestedQty": OperationService._num(ev.get("requestedQty") or ev.get("requested_qty")),
                    "processedQty": OperationService._num(ev.get("processedQty") or ev.get("processed_qty")),

                    "status": ev.get("status") or "Requested",
                    "buyer": ev.get("buyer") or ev.get("buyerName") or ev.get("buyer_name") or "",

                    "productName": ev.get("productName") or ev.get("product_name") or "",
                    "manufacturerName": ev.get("manufacturerName") or ev.get("manufacturer_name") or "",
                    "processingDate": ev.get("processingDate") or ev.get("processing_date") or "",
                    "timestamp": str(ev.get("created_at") or ev.get("timestamp") or ""),
                    "txHash": ev.get("txHash") or ev.get("tx_hash"),
                }

            else:
                status = ev[0] if len(ev) > 0 else "Requested"

                operation = {
                    "operationId": operation_id,
                    "manufacturerId": manufacturer_id,
                    "cropId": ev[1] if len(ev) > 1 else "",
                    "cropName": ev[2] if len(ev) > 2 else "",
                    "cropType": ev[3] if len(ev) > 3 else "",
                    "sowingDate": ev[4] if len(ev) > 4 else "",
                    "harvestDate": ev[5] if len(ev) > 5 else "",
                    "totalQty": OperationService._num(ev[6] if len(ev) > 6 else 0),
                    "requestedQty": OperationService._num(ev[7] if len(ev) > 7 else 0),
                    "processedQty": OperationService._num(ev[8] if len(ev) > 8 else 0),
                    "status": status,
                    "buyer": ev[9] if len(ev) > 9 else "",
                    "productName": ev[10] if len(ev) > 10 else "",
                    "manufacturerName": ev[11] if len(ev) > 11 else "",
                    "processingDate": ev[12] if len(ev) > 12 else "",
                    "timestamp": ev[13] if len(ev) > 13 else "",
                }

        if not operation:
            operation = {
                "operationId": operation_id,
                "manufacturerId": manufacturer_id,
                "cropId": "",
                "cropName": "",
                "cropType": "",
                "sowingDate": "",
                "harvestDate": "",
                "totalQty": 0,
                "requestedQty": 0,
                "processedQty": 0,
                "status": "Unknown",
                "buyer": "",
                "productName": "",
                "manufacturerName": "",
                "processingDate": "",
                "timestamp": "",
            }

        return operation

    @staticmethod
    def get_operation_info(operation_id: str) -> OperationInfoModel:
        data = OperationService.get_operation_detail("", operation_id)
        return OperationInfoModel(**data)

    @staticmethod
    def register_operation_with_blockchain(
        manufacturer_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        model = OperationRegistrationModel(
            manufacturerId=manufacturer_id,
            operationId=payload.get("operationId") or payload.get("operation_id"),

            cropId=payload.get("cropId") or payload.get("crop_id"),
            cropName=payload.get("cropName") or payload.get("crop_name"),
            cropType=payload.get("cropType") or payload.get("crop_type"),

            sowingDate=payload.get("sowingDate") or payload.get("sowing_date") or payload.get("datePlanted"),
            harvestDate=payload.get("harvestDate") or payload.get("harvest_date"),

            totalQty=OperationService._num(payload.get("totalQty") or payload.get("total_qty")),
            requestedQty=OperationService._num(payload.get("requestedQty") or payload.get("requested_qty")),
            processedQty=OperationService._num(payload.get("processedQty") or payload.get("processed_qty")),

            status=payload.get("status") or "Requested",
            buyer=payload.get("buyer") or payload.get("buyerName") or payload.get("buyer_name"),

            productName=payload.get("productName") or payload.get("product_name"),
            manufacturerName=payload.get("manufacturerName") or payload.get("manufacturer_name"),
            processingDate=payload.get("processingDate") or payload.get("processing_date"),
        )

        col = get_col("manufacturer_operations")
        inserted_id = None

        doc = {
            "manufacturer_id": model.manufacturerId,
            "manufacturerId": model.manufacturerId,

            "operation_id": model.operationId,
            "operationId": model.operationId,

            "crop_id": model.cropId,
            "cropId": model.cropId,

            "crop_name": model.cropName,
            "cropName": model.cropName,

            "crop_type": model.cropType,
            "cropType": model.cropType,

            "sowing_date": model.sowingDate,
            "sowingDate": model.sowingDate,

            "harvest_date": model.harvestDate,
            "harvestDate": model.harvestDate,

            "total_qty": model.totalQty,
            "totalQty": model.totalQty,

            "requested_qty": model.requestedQty,
            "requestedQty": model.requestedQty,

            "processed_qty": model.processedQty,
            "processedQty": model.processedQty,

            "status": model.status,
            "buyer": model.buyer,

            "product_name": model.productName,
            "productName": model.productName,

            "manufacturer_name": model.manufacturerName,
            "manufacturerName": model.manufacturerName,

            "processing_date": model.processingDate,
            "processingDate": model.processingDate,

            "created_at": datetime.utcnow(),
        }

        if col is not None:
            try:
                res = col.insert_one(doc)
                inserted_id = res.inserted_id
            except Exception as e:
                print(f"⚠️ Mongo insert manufacturer_operations failed: {e}")

        tx_hash = None

        if register_operation_onchain:
            tx_hash = register_operation_onchain(
                manufacturer_id=model.manufacturerId,
                operation_id=model.operationId,
                crop_id=model.cropId,
                crop_name=model.cropName,
                crop_type=model.cropType or "",
                sowing_date=model.sowingDate or "",
                harvest_date=model.harvestDate or "",
                total_qty=model.totalQty or 0,
                requested_qty=model.requestedQty or 0,
                processed_qty=model.processedQty or 0,
                status=model.status or "Requested",
                buyer=model.buyer or "",
                product_name=model.productName or "",
                manufacturer_name=model.manufacturerName or "",
                processing_date=model.processingDate or "",
            )
        else:
            print("⚠️ register_operation_onchain missing in backend.blockchain")

        if col is not None and inserted_id and tx_hash:
            col.update_one(
                {"_id": inserted_id},
                {
                    "$set": {
                        "txHash": tx_hash,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

        return {
            "ok": True,
            "operationId": model.operationId,
            "cropId": model.cropId,
            "txHash": tx_hash,
            "mongo_saved": bool(inserted_id),
        }