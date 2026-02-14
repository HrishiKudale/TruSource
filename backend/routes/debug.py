from flask import Blueprint, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

trace_bp = Blueprint("rfid_bp", __name__, url_prefix="/rfid")
@trace_bp.get("/debug-token")
def debug_token():
    print("Authorization header:", request.headers.get("Authorization"))
    try:
        verify_jwt_in_request()
        ident = get_jwt_identity()
        print("Decoded identity:", ident)
        return jsonify(ok=True, identity=ident)
    except Exception as e:
        print("JWT ERROR:", str(e))
        return jsonify(ok=False, error=str(e)), 401
