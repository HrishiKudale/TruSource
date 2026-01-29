# app.py (Render + Local working)

from flask import Flask
from flask_cors import CORS
from datetime import timedelta
import os

from flask_jwt_extended import JWTManager

from backend.app_config import load_config
from backend.mongo import init_mongo
from backend.register_blueprints import register_all_blueprints

from backend.services.auth_api_client import warmup


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # -------------------------
    # Config & security
    # -------------------------
    load_config(app)
    app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))
    app.permanent_session_lifetime = timedelta(days=7)

    CORS(app, resources={r"/*": {"origins": "*"}})

    # -------------------------
    # Mongo
    # -------------------------
    DISABLE_MONGO = os.getenv("DISABLE_MONGO", "0") == "1"
    if DISABLE_MONGO:
        print("⚠️ Mongo disabled by DISABLE_MONGO=1")
    else:
        init_mongo(app)
        print("✅ Mongo init attempted")

    # -------------------------
    # JWT
    # -------------------------
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "change-me")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=6)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=14)
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    JWTManager(app)

    # ✅ IMPORTANT: register warmup BEFORE returning app
    @app.before_request
    def _wake_auth_service():
        if os.getenv("USE_REMOTE_AUTH_API", "0") == "1":
            # warmup should be cached internally (not hitting health every request)
            warmup(force=False)

    # -------------------------
    # Blueprints
    # -------------------------
    register_all_blueprints(app)

    return app


# ✅ THIS is what gunicorn needs:
app = create_app()


# Local run only
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
