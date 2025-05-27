import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ИСПРАВЛЕНИЕ ЗДЕСЬ: Измените TOKEN на TELEGRAM_TOKEN
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    MONGO_URI = os.getenv("MONGO_URI")
    DB_NAME = "game_planner"