from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from config import Config
from datetime import datetime

# Инициализация клиента MongoDB
client = AsyncIOMotorClient(Config.MONGO_URI)
db = client[Config.DB_NAME]

# Объявление коллекций
events_collection = db.events
users_collection = db.users
ratings_collection = db.ratings


class UserCRUD:
    @staticmethod
    async def add_user(user_id: int):
        """
        Добавляет пользователя в коллекцию, если его там нет,
        или обновляет поле 'last_seen' для существующего пользователя.
        """
        await users_collection.update_one(
            {"_id": user_id},
            {"$set": {"last_seen": datetime.utcnow()}},
            upsert=True  # Если документа нет, он будет создан
        )

    @staticmethod
    async def get_user(user_id: int):
        """
        Возвращает документ пользователя по его ID.
        """
        return await users_collection.find_one({"_id": user_id})

    @staticmethod
    async def list_all_users():
        """
        Возвращает список всех user_id из коллекции 'users'.
        """
        cursor = users_collection.find({}, {"_id": 1})
        return [user["_id"] async for user in cursor]


class EventCRUD:
    @staticmethod
    async def create(data: dict):
        """
        Создает новое событие в базе данных.
        """
        result = await events_collection.insert_one(data)
        return str(result.inserted_id)

    @staticmethod
    async def get(event_id: str):
        """
        Возвращает событие по его ID.
        """
        return await events_collection.find_one({"_id": ObjectId(event_id)})

    @staticmethod
    async def list_all():
        """
        Возвращает список всех событий, отсортированных по дате.
        """
        cursor = events_collection.find().sort("datetime")
        return [event async for event in cursor]

    @staticmethod
    async def filter_by_date(start, end):
        """
        Возвращает список событий в заданном диапазоне дат.
        """
        cursor = events_collection.find({"datetime": {"$gte": start.isoformat(), "$lte": end.isoformat()}}).sort(
            "datetime")
        return [event async for event in cursor]

    @staticmethod
    async def list_active_exclude_user(user_id: int):
        """
        Возвращает список активных событий (которые еще не прошли) других пользователей.
        """
        now = datetime.utcnow().isoformat()
        cursor = events_collection.find({
            "creator_id": {"$ne": user_id},
            "datetime": {"$gte": now}
        }).sort("datetime")
        return [event async for event in cursor]

    @staticmethod
    async def list_by_creator(creator_id: int):
        """
        Возвращает список всех событий, созданных определенным пользователем.
        """
        cursor = events_collection.find({"creator_id": creator_id}).sort("datetime")
        return [event async for event in cursor]

    @staticmethod
    async def list_participated_by_user(user_id: int):
        """
        Возвращает список всех событий, в которых участвует данный пользователь.
        """
        cursor = events_collection.find({"participants": user_id}).sort("datetime")
        return [event async for event in cursor]

    @staticmethod
    async def add_participant(event_id: str, user_id: int):
        """
        Добавляет участника к событию.
        """
        await events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$addToSet": {"participants": user_id}}
        )
        return await events_collection.find_one({"_id": ObjectId(event_id)})

    @staticmethod
    async def remove_participant(event_id: str, user_id: int):
        """
        Удаляет участника из события.
        """
        await events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$pull": {"participants": user_id}}
        )
        return await events_collection.find_one({"_id": ObjectId(event_id)})

    @staticmethod
    async def update_event(event_id: str, data: dict):
        """
        Обновляет поля события по его ID.
        """
        result = await events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": data}
        )
        return result.modified_count > 0

    @staticmethod
    async def delete_event(event_id: str):
        """
        Удаляет событие по его ID.
        """
        result = await events_collection.delete_one({"_id": ObjectId(event_id)})
        return result.deleted_count > 0


class RatingCRUD:
    @staticmethod
    async def add_rating(event_id: str, creator_id: int, rater_id: int, rating: int):
        """
        Добавляет или обновляет оценку, данную одним пользователем другому
        за конкретное событие.
        """
        await ratings_collection.update_one(
            {
                "event_id": ObjectId(event_id),
                "creator_id": creator_id,
                "rater_id": rater_id
            },
            {"$set": {"rating": rating, "timestamp": datetime.utcnow()}},
            upsert=True
        )

    @staticmethod
    async def get_average_rating(user_id: int):
        """
        Вычисляет средний рейтинг для пользователя, который был оценен (как создатель).
        """
        pipeline = [
            {"$match": {"creator_id": user_id}},
            {"$group": {"_id": "$creator_id", "average_rating": {"$avg": "$rating"}}}
        ]
        result = await ratings_collection.aggregate(pipeline).to_list(length=1)
        return result[0]["average_rating"] if result else 0.0

    @staticmethod
    async def get_all_average_ratings():
        """
        Возвращает список всех пользователей с их средними рейтингами,
        отсортированными по убыванию рейтинга.
        """
        pipeline = [
            # Группируем по creator_id и считаем средний рейтинг для каждого создателя
            {"$group": {"_id": "$creator_id", "average_rating": {"$avg": "$rating"}}},
            # Добавляем информацию о пользователе (например, username или first_name)
            {"$lookup": {
                "from": "users",  # Название коллекции пользователей
                "localField": "_id",
                "foreignField": "_id",
                "as": "user_info"
            }},
            # Разворачиваем массив user_info (т.к. $lookup возвращает массив)
            {"$unwind": "$user_info"},
            # Выбираем нужные поля
            {"$project": {
                "_id": 0,  # Не включаем _id
                "user_id": "$_id",
                "username": "$user_info.username",  # Предполагаем, что username хранится в user_info
                "first_name": "$user_info.first_name",  # Если username нет, используем first_name
                "average_rating": {"$round": ["$average_rating", 2]}  # Округляем до 2 знаков
            }},
            # Сортируем по рейтингу по убыванию
            {"$sort": {"average_rating": -1}}
        ]

        # Получаем все результаты агрегации
        results = await ratings_collection.aggregate(pipeline).to_list(None)
        return results