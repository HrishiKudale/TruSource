"""
Centralized Blueprint Registration
All blueprints MUST be registered inside register_all_blueprints(app)
"""

def register_all_blueprints(app):

    # Root
    from backend.routes.root.root_routes import root_bp
    app.register_blueprint(root_bp)

    # Farmer modules
    from backend.routes.farmer.crop_routes import crop_bp, farm_coord_bp
    from backend.routes.farmer.dashboard_routes import dashboard_bp
    from backend.routes.farmer.logistics_routes import logistics_bp
    from backend.routes.farmer.lot_routes import lot_bp
    from backend.routes.farmer.recall_routes import recall_bp
    from backend.routes.farmer.record_harvest import harvest_bp
    from backend.routes.farmer.sales_routes import sales_bp
    from backend.routes.farmer.storage_routes import storage_bp
    from backend.routes.farmer.processing_routes import processing_bp
    from backend.routes.farmer.marketplace_routes import marketplace_bp
    from backend.routes.media_routes import media_bp
    # app.py / main init
    from backend.routes.farmer.pricing_routes import pricing_bp
    app.register_blueprint(pricing_bp)

    # Register all farmer blueprints
    app.register_blueprint(crop_bp)
    app.register_blueprint(farm_coord_bp)     
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(logistics_bp)
    app.register_blueprint(lot_bp)
    app.register_blueprint(recall_bp)
    app.register_blueprint(harvest_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(storage_bp)
    app.register_blueprint(processing_bp) 
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(media_bp)


    # Auth
    from backend.routes.auth.auth_routes import auth_bp
    app.register_blueprint(auth_bp)

    # QR
    from backend.routes.qr.qr_routes import qr_bp
    app.register_blueprint(qr_bp)

    # RFID
    from backend.routes.rfid.rfid_routes import rfid_bp
    app.register_blueprint(rfid_bp)

    # Traceability
    from backend.routes.traceability.trace_routes import traceability_bp
    app.register_blueprint(traceability_bp)

    print("✓ All blueprints registered")


    from backend.routes.farmer.setting_routes import settings_bp
    app.register_blueprint(settings_bp)

    from backend.routes.debug import trace_bp
    app.register_blueprint(trace_bp)