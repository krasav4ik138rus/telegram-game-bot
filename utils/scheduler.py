from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from telegram.ext import Application
from bson import ObjectId
from database.crud import EventCRUD, UserCRUD  # Импортируем EventCRUD и UserCRUD


async def check_upcoming_events(app: Application):
    now = datetime.utcnow()
    upcoming = EventCRUD.events_collection.find(
        {  # Используем коллекцию напрямую, так как EventCRUD.find() не существует
            "datetime": {
                "$gte": now.isoformat(),  # Ищем события, которые начнутся в ближайшие 30 минут
                "$lte": (now + timedelta(minutes=30)).isoformat()
            },
            "notified_upcoming": {"$ne": True}  # Добавляем флаг, чтобы не отправлять уведомление повторно
        })

    async for event in upcoming:
        participants = event.get("participants", [])
        for user_id in participants:
            try:
                await app.bot.send_message(
                    chat_id=user_id,
                    text=f"🔔 Напоминание: скоро начнется событие '{event['game']}' в {event['datetime']}"
                )
                # Помечаем событие как уведомленное
                await EventCRUD.events_collection.update_one(
                    {"_id": event["_id"]},
                    {"$set": {"notified_upcoming": True}}
                )
            except Exception as e:
                print(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")


async def check_ended_events_for_rating(app: Application):
    now = datetime.utcnow()
    # Ищем события, которые закончились в последние 24 часа и по которым еще не запрашивали оценку
    # Предполагаем, что datetime и duration хранятся в формате, позволяющем их сравнивать
    # Если datetime - строка ISO, а duration - int часов, то нужно преобразовать

    # Можно искать события, которые начались до текущего момента и закончились недавно
    # И не были оценены (добавим поле 'rating_requested' в событие)

    # Получаем все события, которые уже начались
    all_events_cursor = EventCRUD.events_collection.find({
        "datetime": {"$lte": now.isoformat()},
        "rating_requested": {"$ne": True}  # Еще не запрашивали оценку
    })

    async for event in all_events_cursor:
        try:
            event_datetime_str = event.get("datetime")
            event_duration_hours = event.get("duration")

            if not event_datetime_str or not event_duration_hours:
                continue  # Пропускаем, если данные неполные

            event_start_dt = datetime.fromisoformat(event_datetime_str)
            event_end_dt = event_start_dt + timedelta(hours=event_duration_hours)

            # Если событие закончилось и прошло не более 24 часов с момента окончания
            if event_end_dt <= now and (now - event_end_dt) <= timedelta(hours=24):
                participants = event.get("participants", [])
                creator_id = event.get("creator_id")
                event_id = str(event["_id"])

                for participant_id in participants:
                    if participant_id != creator_id:  # Участник не должен оценивать себя
                        try:
                            # Отправляем запрос на оценку
                            await app.bot.send_message(
                                chat_id=participant_id,
                                text=f"Событие '{event['game']}' завершилось. Пожалуйста, оцените создателя ({event.get('creator_name', 'Неизвестен')})!",
                                reply_markup=KeyboardBuilder.build_rating_keyboard(event_id, creator_id)
                                # Новая клавиатура для оценки
                            )
                        except Exception as e:
                            print(f"Ошибка при отправке запроса на оценку пользователю {participant_id}: {e}")

                # Помечаем событие как "оценка запрошена"
                await EventCRUD.events_collection.update_one(
                    {"_id": event["_id"]},
                    {"$set": {"rating_requested": True}}
                )

        except Exception as e:
            print(f"Ошибка при обработке завершившегося события {event.get('_id')}: {e}")


def setup_scheduler(app: Application):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_upcoming_events, 'interval', minutes=5, args=[app])
    scheduler.add_job(check_ended_events_for_rating, 'interval', hours=1,
                      args=[app])  # Проверяем завершившиеся события каждый час
    scheduler.start()