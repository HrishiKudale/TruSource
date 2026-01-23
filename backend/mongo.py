from flask_pymongo import PyMongo

mongo = PyMongo()

def init_mongo(app):
    # Mongo URI comes from app.config (set in config.py)
    mongo.init_app(app)
    return mongo
