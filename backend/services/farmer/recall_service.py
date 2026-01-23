# backend/services/farmer/recall_service.py

from blockchain_setup import recall_contract, web3
from flask import jsonify


class RecallService:

    @staticmethod
    def get_recall_events(farmer_id: str, span_blocks: int = 2_000_000,
                          from_block: int = None, to_block: int = None):
        """
        Fetch recall events for the crops belonging to this farmer.
        """

        latest = web3.eth.block_number

        if from_block is None:
            from_block = max(1, latest - span_blocks)
        if to_block is None:
            to_block = latest

        try:
            event_filter = recall_contract.events.RecallFiled.create_filter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={"farmerId": farmer_id}
            )

            events = []
            for ev in event_filter.get_all_entries():
                decoded = {
                    "txHash": ev.transactionHash.hex(),
                    "cropId": ev.args.cropId,
                    "batchCode": ev.args.batchCode,
                    "severity": ev.args.severity,
                    "expiresAt": ev.args.expiresAt,
                    "reasonURI": ev.args.reasonURI,
                }
                events.append(decoded)

            return jsonify({"ok": True, "events": events})

        except Exception as e:
            return jsonify({"ok": False, "err": str(e)})
