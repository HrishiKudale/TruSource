# backend/mongo.py
from flask_pymongo import PyMongo

mongo = PyMongo()


def init_mongo(app):
    """
    Initializes Flask-PyMongo.
    Needs app.config["MONGO_URI"] (or app.config.from_env etc.)
    """
    mongo.init_app(app)

    # Optional sanity log:
    try:
        _ = mongo.db  # triggers db property
        print("✅ Mongo initialized")
    except Exception as e:
        print(f"⚠️ Mongo init attempted but failed: {e}")

    return mongo
