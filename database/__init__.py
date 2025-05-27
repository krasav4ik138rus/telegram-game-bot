from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_URI)
db = client[Config.DB_NAME]

events_collection = db.events
users_collection = db.users
ratings_collection = db.ratings
