from flask_pymongo import PyMongo

mongo = PyMongo()

def init_mongo(app):
    # Replace with your Atlas URI
    app.config["MONGO_URI"] = "mongodb+srv://precisiontraceability_db_user:RqT4DWJAi3FeEXUd@traceability.c9crsed.mongodb.net/"
    mongo.init_app(app)
    return mongo
