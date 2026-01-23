# backend/mongo.py
from flask_pymongo import PyMongo

mongo = PyMongo()

def init_mongo(app):
    app.config["MONGO_URI"] = app.config.get("MONGO_URI")
    mongo.init_app(app)
    return mongo
