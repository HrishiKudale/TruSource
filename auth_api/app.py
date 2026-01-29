import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from auth_routes import auth_bp, bcrypt  # ✅ correct for Root Directory = auth_api

def create_app():
    app = Flask(__name__)
    CORS(app)

    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "change-this")
    JWTManager(app)

    bcrypt.init_app(app)
    app.register_blueprint(auth_bp)

    # ✅ Debug: print all registered routes once at boot
    print("✅ Registered routes:")
    for r in app.url_map.iter_rules():
        print(r, r.methods)

    return app

app = create_app()
