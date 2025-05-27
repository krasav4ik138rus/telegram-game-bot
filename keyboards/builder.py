from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import calendar  # Импортируем модуль calendar


class KeyboardBuilder:
    @staticmethod
    def main_menu():
        return ReplyKeyboardMarkup([
            ["🎮 Создать событие", "👀 Активные события"],
            ["⚙️ Мои события", "⭐ Топ игроков"]
        ], resize_keyboard=True)

    @staticmethod
    def filter_menu():
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Сегодня", callback_data="filter_today"),
                InlineKeyboardButton("Завтра", callback_data="filter_tomorrow"),
                InlineKeyboardButton("Все", callback_data="filter_all")
            ]
        ])

    @staticmethod
    def event_actions(event_id: str):
        """
        Клавиатура для действий с событием, когда пользователь уже взаимодействует с ним.
        Например, для уведомлений или в списке 'Мои события', где не нужна кнопка 'Присоединиться'.
        Кнопка 'Присоединиться' обрабатывается отдельно в active_events_list.
        """
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Подробнее", callback_data=f"info_{event_id}")
            ]
        ])

    @staticmethod
    def build_calendar(year: int, month: int) -> InlineKeyboardMarkup:
        keyboard = []

        # Заголовок с месяцем и годом
        month_year_str = datetime(year, month, 1).strftime("%B %Y")
        keyboard.append([InlineKeyboardButton(month_year_str, callback_data="ignore")])

        # Дни недели, понедельник первый
        days_of_week = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in days_of_week])

        # Получаем календарь для месяца
        cal = calendar.monthcalendar(year, month)
        for week in cal:
            row = []
            for day in week:
                if day == 0:  # Пустые дни в начале или конце месяца
                    row.append(InlineKeyboardButton(" ", callback_data="ignore"))
                else:
                    # Опционально: выделить текущий день
                    today = datetime.now().day if datetime.now().year == year and datetime.now().month == month else -1
                    button_text = f"*{day}*" if day == today else str(day)
                    row.append(InlineKeyboardButton(button_text, callback_data=f"day_{year}_{month}_{day}"))
            keyboard.append(row)

        # Кнопки для навигации по месяцам
        keyboard.append([
            InlineKeyboardButton("◀️", callback_data=f"prev_month_{year}_{month}"),
            InlineKeyboardButton(" ", callback_data="ignore"),  # Пустая кнопка для центрирования
            InlineKeyboardButton("▶️", callback_data=f"next_month_{year}_{month}")
        ])

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def build_time_keyboard() -> InlineKeyboardMarkup:
        keyboard = []
        times = []
        for hour in range(0, 24):
            for minute in [0, 30]:  # Шаг в 30 минут
                times.append(f"{hour:02d}:{minute:02d}")

        # Распределяем время по 4 кнопки в ряд
        for i in range(0, len(times), 4):
            row = []
            for time_slot in times[i:i + 4]:
                row.append(InlineKeyboardButton(time_slot, callback_data=f"time_{time_slot}"))
            keyboard.append(row)

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def build_game_choice_keyboard() -> InlineKeyboardMarkup:
        # Обновленный, более общий список игр
        games = ["Dota 2", "CS2", "Valorant", "League of Legends", "Minecraft", "Fortnite", "Apex Legends", "PUBG",
                 "Genshin Impact", "Другое"]
        keyboard = []

        # Размещаем по 2 игры в ряд
        for i in range(0, len(games), 2):
            row = []
            row.append(InlineKeyboardButton(games[i], callback_data=f"game_{games[i]}"))
            if i + 1 < len(games):
                row.append(InlineKeyboardButton(games[i + 1], callback_data=f"game_{games[i + 1]}"))
            keyboard.append(row)

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def active_events_list(events: list, user_id: int) -> InlineKeyboardMarkup:
        """
        Создаёт inline-клавиатуру со списком событий.
        Каждое событие - кнопка с названием, описанием, датой/временем, количеством участников и создателем.
        Вторая кнопка 'Присоединиться', 'Вы участвуете' или 'Мест нет'.
        """
        keyboard = []
        for event in events:
            event_id = str(event["_id"])
            game = event.get("game", "Без названия")
            datetime_str = event.get("datetime", "")
            creator = event.get("creator_name", "Неизвестен")
            participants = event.get("participants", [])
            count = len(participants)
            description = event.get("description", "Нет описания")  # Новое поле
            limit = event.get("participant_limit", 0)  # Новое поле

            # Форматируем дату и время
            try:
                dt_object = datetime.fromisoformat(datetime_str)
                formatted_datetime = dt_object.strftime("%d.%m.%Y %H:%M")
            except ValueError:
                formatted_datetime = datetime_str

            # Текст для отображения лимита
            limit_text = f" / {limit}" if limit > 0 else " / ∞"

            # Текст для кнопки информации о событии
            text_button = (
                f"🎮 {game}\n"
                f"📝 Описание: {description}\n"  # Добавлено
                f"📅 {formatted_datetime}\n"
                f"👥 Участников: {count}{limit_text}\n"  # Обновлено
                f"Создатель: {creator}"
            )

            # Добавляем кнопку с деталями события
            keyboard.append([InlineKeyboardButton(text_button, callback_data=f"info_{event_id}")])

            # Логика для кнопки присоединения/участия/нет мест
            if user_id in participants:
                keyboard.append(
                    [InlineKeyboardButton(f"✅ Вы участвуете ({count}{limit_text})", callback_data=f"info_{event_id}")])
            elif limit > 0 and count >= limit:  # Если есть лимит и он достигнут
                keyboard.append(
                    [InlineKeyboardButton(f"🚫 Мест нет ({count}{limit_text})", callback_data=f"info_{event_id}")])
            else:  # Если пользователь не участвует и есть места
                keyboard.append(
                    [InlineKeyboardButton(f"➕ Присоединиться ({count}{limit_text})", callback_data=f"join_{event_id}")])

            # Добавляем разделитель для лучшей читаемости
            keyboard.append([InlineKeyboardButton("—" * 30, callback_data="ignore")])

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def build_rating_keyboard(event_id: str, creator_id: int) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру для оценки создателя события.
        """
        keyboard = [
            [InlineKeyboardButton("1⭐", callback_data=f"rate_event_{event_id}_{creator_id}"),
             InlineKeyboardButton("2⭐", callback_data=f"rate_event_{event_id}_{creator_id}"),
             InlineKeyboardButton("3⭐", callback_data=f"rate_event_{event_id}_{creator_id}"),
             InlineKeyboardButton("4⭐", callback_data=f"rate_event_{event_id}_{creator_id}"),
             InlineKeyboardButton("5⭐", callback_data=f"rate_event_{event_id}_{creator_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)