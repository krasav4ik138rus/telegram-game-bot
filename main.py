import logging
import nest_asyncio
import asyncio
from telegram.ext import Application

from config import Config
from handlers import start, events, ratings  # Убедитесь, что все хэндлеры импортированы
from utils.scheduler import setup_scheduler

nest_asyncio.apply()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Уменьшаем уровень логирования для httpx, чтобы избежать слишком много отладочных сообщений
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main():
    # Инициализация Persistence для сохранения состояний между перезапусками бота.
    # Файл 'persistence.json' будет создан в корневой папке проекта.
    persistence = None

    app = Application.builder().token(Config.TELEGRAM_TOKEN).persistence(persistence).build()

    # Порядок регистрации важен для некоторых обработчиков (например, start)
    start.register_handlers(app)
    events.register_handlers(app)
    ratings.register_handlers(app)

    # Установка планировщика задач для напоминаний о событиях
    setup_scheduler(app)

    # Запускаем бота. run_polling() сама вызывает app.initialize() при использовании persistence.
    await app.run_polling()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())