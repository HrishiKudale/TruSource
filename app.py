# app.py (FINAL CLEAN VERSION)

from flask import Flask
from flask_cors import CORS
from datetime import timedelta
import os

# -----------------------------
#  INTERNAL MODULE SETUP
# -----------------------------
from backend.app_config import load_config
from backend.mongo import init_mongo
from backend.blockchain import init_blockchain
from backend.register_blueprints import register_all_blueprints

# -----------------------------
#  JWT (Used for Mobile App)
# -----------------------------
from flask_jwt_extended import JWTManager

def create_app():
    # ------------------------------------------
    # Flask setup
    # ------------------------------------------
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )
    

    # ------------------------------------------
    # Load config & security
    # ------------------------------------------
    load_config(app)

    app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))
    app.permanent_session_lifetime = timedelta(days=7)

    # CORS for React Native mobile app
    CORS(app, resources={r"/*": {"origins": "*"}})

    # ------------------------------------------
    # Mongo & Blockchain
    # ------------------------------------------
    init_mongo(app)        # connects mongo + printlos ✓
    init_blockchain(app)   # loads contract + prints ✓

    # ------------------------------------------
    # JWT setup
    # ------------------------------------------
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "change-me")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"]  = timedelta(hours=6)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=14)
    app.config["JWT_TOKEN_LOCATION"]        = ["headers"]
    app.config["JWT_HEADER_TYPE"]           = "Bearer"

    JWTManager(app)

    # ------------------------------------------
    # Blueprint Registration
    # Clean, modular, plug-and-play
    # ------------------------------------------
    register_all_blueprints(app)

    # ------------------------------------------
    # Return ready app
    # ------------------------------------------
    return app


# -----------------------------
#  ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True  # ❗ Disable in production
    )
