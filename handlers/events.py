from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)
from datetime import datetime, timedelta
from database.crud import EventCRUD, UserCRUD, RatingCRUD  # Добавляем UserCRUD и RatingCRUD
from keyboards.builder import KeyboardBuilder

# Состояния для создания события
DATE, TIME, GAME, DESCRIPTION, PARTICIPANT_LIMIT = range(5)  # Новые состояния, DURATION удален

# Состояния для редактирования события
EDIT_CHOICE, EDIT_DATE, EDIT_TIME, EDIT_GAME, EDIT_DESCRIPTION, EDIT_LIMIT = range(6)

# Состояния для рейтинга
RATING = range(1)


async def show_event_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 Выберите фильтр:",
        reply_markup=KeyboardBuilder.filter_menu()
    )


async def apply_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    filter_type = query.data.split("_")[1]

    now = datetime.utcnow()  # Используем UTC для консистентности с сохранением в БД
    if filter_type == "today":
        start = datetime(now.year, now.month, now.day)
        end = datetime(now.year, now.month, now.day, 23, 59, 59)
    elif filter_type == "tomorrow":
        tomorrow = now + timedelta(days=1)
        start = datetime(tomorrow.year, tomorrow.month, tomorrow.day)
        end = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 23, 59, 59)
    else:  # filter_all
        start = datetime.min  # Минимальная дата для всех
        end = datetime.max  # Максимальная дата для всех

    events = await EventCRUD.list_all()  # Получаем все события, затем фильтруем

    filtered_events = []
    for e in events:
        try:
            event_dt = datetime.fromisoformat(e['datetime'])
            if start <= event_dt <= end:
                filtered_events.append(e)
        except ValueError:
            # Обработка событий с некорректной датой, можно логировать или пропустить
            pass

    # Отфильтруем только активные события, которые еще не прошли
    active_filtered_events = [
        e for e in filtered_events
        if datetime.fromisoformat(e['datetime']) >= datetime.utcnow()
    ]

    if not active_filtered_events:
        await query.message.reply_text("❌ Активных событий по выбранному фильтру не найдено.")
        return

    # Изменили цикл для использования active_events_list
    keyboard = KeyboardBuilder.active_events_list(active_filtered_events, query.from_user.id)
    await query.message.reply_text(
        "Вот список событий:",
        reply_markup=keyboard
    )


async def create_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    calendar = KeyboardBuilder.build_calendar(now.year, now.month)
    # Запоминаем текущий месяц/год в user_data для навигации
    context.user_data['calendar_year'] = now.year
    context.user_data['calendar_month'] = now.month
    await update.message.reply_text("📅 Выберите дату для события:", reply_markup=calendar)
    return DATE


async def date_time_picker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'ignore':
        return DATE

    if data.startswith("prev_month_"):
        _, _, year, month = data.split("_")
        year = int(year)
        month = int(month)

        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1

        context.user_data['calendar_year'] = year
        context.user_data['calendar_month'] = month
        calendar = KeyboardBuilder.build_calendar(year, month)
        await query.edit_message_reply_markup(reply_markup=calendar)
        return DATE

    if data.startswith("next_month_"):
        _, _, year, month = data.split("_")
        year = int(year)
        month = int(month)

        if month == 12:
            month = 1
            year += 1
        else:
            month += 1

        context.user_data['calendar_year'] = year
        context.user_data['calendar_month'] = month
        calendar = KeyboardBuilder.build_calendar(year, month)
        await query.edit_message_reply_markup(reply_markup=calendar)
        return DATE

    if data.startswith('day_'):
        _, year, month, day = data.split('_')
        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        context.user_data['datetime_date'] = date_str

        await query.edit_message_text(
            f"Дата выбрана: {date_str}\nТеперь выберите время:",
            reply_markup=KeyboardBuilder.build_time_keyboard()
        )
        return TIME

    if data.startswith('time_'):
        time_str = data.split('_')[1]
        date_str = context.user_data.get('datetime_date')
        if not date_str:
            await query.edit_message_text("Ошибка: сначала выберите дату.")
            return DATE

        full_datetime = f"{date_str} {time_str}"
        context.user_data['datetime'] = full_datetime

        await query.edit_message_text(
            f"Вы выбрали дату и время: {full_datetime}\n🎮 Выберите игру:",
            reply_markup=KeyboardBuilder.build_game_choice_keyboard()
        )
        return GAME

    return DATE


async def process_game_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("game_"):
        await query.message.reply_text("Пожалуйста, выберите игру, используя кнопки.")
        return GAME

    game = data[len("game_"):]
    context.user_data["game"] = game

    await query.edit_message_text(
        f"Вы выбрали игру: {game}\n📝 Теперь введите краткое описание события (например, 'Нужен микрофон, играем на новой карте'):"
    )
    return DESCRIPTION  # Переходим к новому состоянию


async def process_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text
    context.user_data["description"] = description

    await update.message.reply_text("👥 Введите максимальное количество участников (0 для безлимита):")
    return PARTICIPANT_LIMIT  # Переходим к новому состоянию


async def process_participant_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        limit = int(update.message.text)
        if limit < 0:
            await update.message.reply_text("❌ Количество участников не может быть отрицательным. Введите число.")
            return PARTICIPANT_LIMIT

        context.user_data["participant_limit"] = limit
        context.user_data["participants"] = [update.message.from_user.id]  # Создатель всегда первый участник

        # Данные создателя
        context.user_data["creator_id"] = update.message.from_user.id
        creator_name = update.message.from_user.full_name
        if not creator_name:
            creator_name = update.message.from_user.first_name
            if not creator_name:
                creator_name = f"Пользователь {update.message.from_user.id}"
        context.user_data["creator_name"] = creator_name

        # Здесь сохраняем событие
        new_event_id = await EventCRUD.create(context.user_data)
        await update.message.reply_text("✅ Событие создано!")

        # --- Уведомление о новом событии ---
        new_event = await EventCRUD.get(new_event_id)
        if new_event:
            all_users = await UserCRUD.list_all_users()

            # Форматируем лимит для отображения
            display_limit = new_event.get('participant_limit', 0)
            limit_text_for_display = f" / {display_limit}" if display_limit > 0 else " / ∞"

            notification_text = (
                f"🎉 Новое событие создано!\n"
                f"🎮 Игра: {new_event.get('game', 'Без названия')}\n"
                f"📝 Описание: {new_event.get('description', 'Нет')}\n"
                f"👥 Участников: {len(new_event.get('participants', []))}{limit_text_for_display}\n"
                f"📅 Дата и время: {datetime.fromisoformat(new_event.get('datetime', '')).strftime('%d.%m.%Y %H:%M')}\n"
                f"Создатель: {new_event.get('creator_name', 'Неизвестен')}"
            )
            for user_id in all_users:
                if user_id != update.message.from_user.id:  # Не отправляем создателю, он уже получил подтверждение
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=notification_text,
                            reply_markup=KeyboardBuilder.event_actions(new_event_id)  # Кнопки присоединиться/подробнее
                        )
                    except Exception as e:
                        print(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
        # --- Конец уведомления ---

        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите число для лимита. Попробуйте еще раз.")
        return PARTICIPANT_LIMIT


async def cancel_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Создание события отменено.")
    return ConversationHandler.END


async def join_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = query.data.split("_")[1]
    user_id = query.from_user.id

    event = await EventCRUD.get(event_id)
    if not event:
        await query.message.reply_text("❌ Событие не найдено.")
        return

    # Проверяем, является ли пользователь создателем события
    if event.get("creator_id") == user_id:
        await query.message.reply_text("Вы не можете присоединиться к своему собственному событию.")
        return

    # Проверяем, участвует ли пользователь уже в событии
    if user_id in event.get("participants", []):
        await query.message.reply_text("Вы уже участвуете в этом событии!")
        return

    # Проверяем лимит участников
    current_participants_count = len(event.get("participants", []))
    participant_limit = event.get("participant_limit", 0)
    if participant_limit > 0 and current_participants_count >= participant_limit:
        await query.message.reply_text("Извините, все места в этом событии уже заняты.")
        return

    updated_event = await EventCRUD.add_participant(event_id, user_id)
    participants_count = len(updated_event.get("participants", []))

    display_limit = updated_event.get('participant_limit', 0)
    limit_text_for_display = f" / {display_limit}" if display_limit > 0 else " / ∞"

    # Обновляем сообщение с кнопками, чтобы показать актуальное количество участников
    await query.message.edit_reply_markup(reply_markup=KeyboardBuilder.event_actions(str(updated_event["_id"])))
    await query.message.reply_text(
        f"✅ Вы присоединились к '{updated_event['game']}'! Теперь участников: {participants_count}{limit_text_for_display}",
    )


async def event_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = query.data.split("_")[1]

    event = await EventCRUD.get(event_id)
    if not event:
        await query.message.reply_text("❌ Событие не найдено.")
        return

    # Форматируем дату и время для более читабельного вида
    datetime_str = event.get("datetime", "")
    try:
        dt_object = datetime.fromisoformat(datetime_str)
        formatted_datetime = dt_object.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        formatted_datetime = datetime_str  # Если формат не ISO, оставляем как есть

    description = event.get("description", "Нет описания")  # Добавлено
    limit = event.get("participant_limit", 0)  # Добавлено

    limit_text = f" / {limit}" if limit > 0 else " / ∞"

    text = (
        f"🎮 {event['game']}\n"
        f"📝 Описание: {description}\n"  # Добавлено
        f"📅 {formatted_datetime}\n"
        f"👥 Участников: {len(event.get('participants', []))}{limit_text}\n"  # Обновлено
        f"Создатель: {event.get('creator_name', 'Неизвестен')}"
    )
    await query.message.reply_text(text)


async def my_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Получаем события, созданные пользователем
    created_events = await EventCRUD.list_by_creator(user_id)
    # Получаем события, в которых пользователь участвует
    participated_events = await EventCRUD.list_participated_by_user(user_id)

    # Используем словарь для хранения уникальных событий по ID
    all_user_events_dict = {}
    for event in created_events:
        all_user_events_dict[str(event["_id"])] = event
    for event in participated_events:
        # Добавляем или перезаписываем, если событие уже есть (например, если пользователь и создатель, и участник)
        all_user_events_dict[str(event["_id"])] = event

        # Преобразуем обратно в список для сортировки
    all_user_events = list(all_user_events_dict.values())
    all_user_events.sort(key=lambda e: datetime.fromisoformat(e.get("datetime", datetime.min.isoformat())))

    if not all_user_events:
        await update.message.reply_text("😔 Вы пока не создали и не участвуете ни в одном событии.")
        return

    await update.message.reply_text("Вот список ваших событий:")
    for event_id, event in all_user_events_dict.items():
        datetime_str = event.get("datetime", "")
        try:
            dt_object = datetime.fromisoformat(datetime_str)
            formatted_datetime = dt_object.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            formatted_datetime = datetime_str

        status_text = ""
        is_creator = False
        if event.get("creator_id") == user_id:
            status_text = "(Создатель)"
            is_creator = True
        elif user_id in event.get("participants", []):
            status_text = "(Участник)"

        description = event.get("description", "Нет описания")  # Добавлено
        limit = event.get("participant_limit", 0)  # Добавлено
        limit_text = f" / {limit}" if limit > 0 else " / ∞"

        text = (
            f"🎮 {event['game']} {status_text}\n"
            f"📝 Описание: {description}\n"  # Добавлено
            f"📅 {formatted_datetime}\n"
            f"👥 Участников: {len(event.get('participants', []))}{limit_text}\n"  # Обновлено
            f"Создатель: {event.get('creator_name', 'Неизвестен')}"
        )

        # Добавляем кнопки управления только для созданных событий
        if is_creator:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_event_{event_id}")],
                [InlineKeyboardButton("🗑️ Отменить", callback_data=f"cancel_event_{event_id}")]
            ])
            await update.message.reply_text(text, reply_markup=keyboard)
        else:
            # Для участников - просто информация или кнопки присоединения/подробнее
            await update.message.reply_text(text, reply_markup=KeyboardBuilder.event_actions(str(event["_id"])))


async def active_events_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    events = await EventCRUD.list_active_exclude_user(user_id)  # Используем новый метод

    if not events:
        await update.message.reply_text("❌ Активных событий других пользователей не найдено.")
        return

    keyboard = KeyboardBuilder.active_events_list(events,
                                                  user_id)  # Передаем user_id для правильного отображения кнопки
    await update.message.reply_text(
        "Вот список активных событий, созданных другими пользователями:",
        reply_markup=keyboard
    )


# Обработчик для запроса оценки
async def request_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, event_id, creator_id = query.data.split("_")

    context.user_data['rating_event_id'] = event_id
    context.user_data['rating_creator_id'] = int(creator_id)  # Сохраняем ID создателя для оценки

    await query.message.reply_text("Пожалуйста, оцените создателя события от 1 до 5:")
    return RATING


# Обработчик для получения оценки
async def process_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rating = int(update.message.text)
        if not (1 <= rating <= 5):
            await update.message.reply_text("❌ Оценка должна быть числом от 1 до 5. Попробуйте еще раз.")
            return RATING

        event_id = context.user_data.get('rating_event_id')
        creator_id = context.user_data.get('rating_creator_id')
        rater_id = update.message.from_user.id

        if not event_id or not creator_id:
            await update.message.reply_text("Произошла ошибка при обработке оценки. Пожалуйста, попробуйте позже.")
            return ConversationHandler.END

        await RatingCRUD.add_rating(event_id, creator_id, rater_id, rating)
        await update.message.reply_text("✅ Ваша оценка принята! Спасибо!")

        # Очищаем данные из user_data
        context.user_data.pop('rating_event_id', None)
        context.user_data.pop('rating_creator_id', None)

        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите число. Попробуйте еще раз.")
        return RATING


# --- НОВЫЕ ОБРАБОТЧИКИ ДЛЯ РЕДАКТИРОВАНИЯ СОБЫТИЙ ---
async def edit_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = query.data.split("_")[2]  # edit_event_<event_id>

    event = await EventCRUD.get(event_id)
    if not event:
        await query.message.reply_text("❌ Событие не найдено.")
        return ConversationHandler.END

    if event.get("creator_id") != query.from_user.id:
        await query.message.reply_text("🚫 Вы не можете редактировать это событие, так как не являетесь его создателем.")
        return ConversationHandler.END

    context.user_data['event_to_edit'] = event  # Сохраняем событие для редактирования

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Дату и Время", callback_data="edit_field_datetime")],
        [InlineKeyboardButton("🎮 Игру", callback_data="edit_field_game")],
        [InlineKeyboardButton("📝 Описание", callback_data="edit_field_description")],
        [InlineKeyboardButton("👥 Лимит участников", callback_data="edit_field_limit")],
        [InlineKeyboardButton("🚫 Отмена", callback_data="edit_cancel")]
    ])
    await query.message.reply_text(f"Что вы хотите изменить в событии '{event.get('game', 'Без названия')}'?",
                                   reply_markup=keyboard)
    return EDIT_CHOICE


async def edit_field_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split("_")[2]  # edit_field_<choice>
    event_to_edit = context.user_data.get('event_to_edit')

    if not event_to_edit:
        await query.message.reply_text("Ошибка: событие для редактирования не найдено.")
        return ConversationHandler.END

    if choice == "datetime":
        now = datetime.now()
        calendar = KeyboardBuilder.build_calendar(now.year, now.month)
        context.user_data['calendar_year'] = now.year
        context.user_data['calendar_month'] = now.month
        await query.edit_message_text("Выберите новую дату для события:", reply_markup=calendar)
        return EDIT_DATE
    elif choice == "game":
        await query.edit_message_text("Выберите новую игру:", reply_markup=KeyboardBuilder.build_game_choice_keyboard())
        return EDIT_GAME
    elif choice == "description":
        await query.edit_message_text("Введите новое описание события:")
        return EDIT_DESCRIPTION
    elif choice == "limit":
        await query.edit_message_text("Введите новый лимит участников (0 для безлимита):")
        return EDIT_LIMIT
    elif choice == "cancel":
        await query.message.reply_text("Редактирование отменено.")
        return ConversationHandler.END
    return EDIT_CHOICE  # Остаемся в этом состоянии, если выбор не обработан


async def edit_datetime_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'ignore':
        return EDIT_DATE

    event_to_edit = context.user_data.get('event_to_edit')
    if not event_to_edit:
        await query.edit_message_text("Ошибка: событие для редактирования не найдено.")
        return ConversationHandler.END

    if data.startswith("prev_month_") or data.startswith("next_month_"):
        _, _, year, month = data.split("_")
        year = int(year)
        month = int(month)

        if data.startswith("prev_month_"):
            if month == 1:
                month = 12; year -= 1
            else:
                month -= 1
        else:  # next_month_
            if month == 12:
                month = 1; year += 1
            else:
                month += 1
        context.user_data['calendar_year'] = year
        context.user_data['calendar_month'] = month
        calendar = KeyboardBuilder.build_calendar(year, month)
        await query.edit_message_reply_markup(reply_markup=calendar)
        return EDIT_DATE

    if data.startswith('day_'):
        _, year, month, day = data.split('_')
        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        context.user_data['edit_datetime_date'] = date_str  # Сохраняем временно

        await query.edit_message_text(
            f"Новая дата выбрана: {date_str}\nТеперь выберите новое время:",
            reply_markup=KeyboardBuilder.build_time_keyboard()
        )
        return EDIT_TIME

    if data.startswith('time_'):
        time_str = data.split('_')[1]
        date_str = context.user_data.get('edit_datetime_date')
        if not date_str:
            await query.edit_message_text("Ошибка: сначала выберите дату.")
            return EDIT_DATE

        full_datetime = f"{date_str} {time_str}"

        updated = await EventCRUD.update_event(
            str(event_to_edit["_id"]),
            {"datetime": full_datetime}
        )
        if updated:
            await query.edit_message_text(f"✅ Дата и время события обновлены на: {full_datetime}")
            # Обновляем сохраненное событие в user_data, чтобы последующие изменения работали с актуальными данными
            updated_event_data = await EventCRUD.get(str(event_to_edit["_id"]))
            context.user_data['event_to_edit'] = updated_event_data
        else:
            await query.edit_message_text("❌ Не удалось обновить дату и время.")
        return ConversationHandler.END
    return EDIT_DATE


async def edit_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = query.data.split('_')[1]  # game_<game_name>

    event_to_edit = context.user_data.get('event_to_edit')
    if not event_to_edit:
        await query.edit_message_text("Ошибка: событие для редактирования не найдено.")
        return ConversationHandler.END

    updated = await EventCRUD.update_event(
        str(event_to_edit["_id"]),
        {"game": game}
    )
    if updated:
        await query.edit_message_text(f"✅ Игра события обновлена на: {game}")
        updated_event_data = await EventCRUD.get(str(event_to_edit["_id"]))
        context.user_data['event_to_edit'] = updated_event_data
    else:
        await query.edit_message_text("❌ Не удалось обновить игру.")
    return ConversationHandler.END


async def edit_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text

    event_to_edit = context.user_data.get('event_to_edit')
    if not event_to_edit:
        await update.message.reply_text("Ошибка: событие для редактирования не найдено.")
        return ConversationHandler.END

    updated = await EventCRUD.update_event(
        str(event_to_edit["_id"]),
        {"description": description}
    )
    if updated:
        await update.message.reply_text(f"✅ Описание события обновлено: {description}")
        updated_event_data = await EventCRUD.get(str(event_to_edit["_id"]))
        context.user_data['event_to_edit'] = updated_event_data
    else:
        await update.message.reply_text("❌ Не удалось обновить описание.")
    return ConversationHandler.END


async def edit_limit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        limit = int(update.message.text)
        if limit < 0:
            await update.message.reply_text("❌ Количество участников не может быть отрицательным. Введите число.")
            return EDIT_LIMIT

        event_to_edit = context.user_data.get('event_to_edit')
        if not event_to_edit:
            await update.message.reply_text("Ошибка: событие для редактирования не найдено.")
            return ConversationHandler.END

        updated = await EventCRUD.update_event(
            str(event_to_edit["_id"]),
            {"participant_limit": limit}
        )
        if updated:
            await update.message.reply_text(f"✅ Лимит участников обновлен на: {limit if limit > 0 else 'Безлимит'}")
            updated_event_data = await EventCRUD.get(str(event_to_edit["_id"]))
            context.user_data['event_to_edit'] = updated_event_data
        else:
            await update.message.reply_text("❌ Не удалось обновить лимит.")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите число. Попробуйте еще раз.")
        return EDIT_LIMIT


async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Этот обработчик может быть вызван как CallbackQuery, так и MessageHandler
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("Редактирование отменено.")
    else:
        await update.message.reply_text("Редактирование отменено.")
    return ConversationHandler.END


# --- НОВЫЕ ОБРАБОТЧИКИ ДЛЯ ОТМЕНЫ СОБЫТИЯ ---
async def cancel_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = query.data.split("_")[2]  # cancel_event_<event_id>

    event = await EventCRUD.get(event_id)
    if not event:
        await query.message.reply_text("❌ Событие не найдено.")
        return

    if event.get("creator_id") != query.from_user.id:
        await query.message.reply_text("🚫 Вы не можете отменить это событие, так как не являетесь его создателем.")
        return

    # Подтверждение отмены
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить отмену", callback_data=f"confirm_cancel_event_{event_id}")],
        [InlineKeyboardButton("🚫 Не отменять", callback_data="do_not_cancel_event")]
    ])
    await query.message.reply_text(f"Вы уверены, что хотите отменить событие '{event.get('game', 'Без названия')}'?",
                                   reply_markup=keyboard)


async def confirm_cancel_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = query.data.split("_")[3]  # confirm_cancel_event_<event_id>

    event = await EventCRUD.get(event_id)
    if not event:
        await query.message.reply_text("❌ Событие не найдено.")
        return

    deleted = await EventCRUD.delete_event(event_id)
    if deleted:
        await query.message.edit_text(f"✅ Событие '{event.get('game', 'Без названия')}' отменено.")
        # Уведомляем участников
        participants = event.get("participants", [])
        for participant_id in participants:
            if participant_id != event.get("creator_id"):  # Не уведомляем создателя
                try:
                    await context.bot.send_message(
                        chat_id=participant_id,
                        text=f"🚨 Внимание: Событие '{event.get('game', 'Без названия')}' (создатель: {event.get('creator_name', 'Неизвестен')}) было ОТМЕНЕНО."
                    )
                except Exception as e:
                    print(f"Ошибка при уведомлении пользователя {participant_id} об отмене: {e}")
    else:
        await query.message.edit_text("❌ Не удалось отменить событие.")


async def do_not_cancel_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Отмена события отменена. Событие остается активным.")


def register_handlers(application):
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🎮 Создать событие$"), create_event)],
        states={
            DATE: [CallbackQueryHandler(date_time_picker_handler)],
            TIME: [CallbackQueryHandler(date_time_picker_handler)],
            GAME: [CallbackQueryHandler(process_game_choice)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_description)],  # Новое состояние
            PARTICIPANT_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_participant_limit)],
            # Новое состояние
        },
        fallbacks=[MessageHandler(filters.Regex("^(Отмена|cancel)$"), cancel_creation)],
        persistent=False,
        name="event_creation_conversation",
    )

    edit_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_event_start, pattern=r"^edit_event_\w+$")],
        states={
            EDIT_CHOICE: [CallbackQueryHandler(edit_field_choice, pattern=r"^edit_field_\w+$")],
            EDIT_DATE: [CallbackQueryHandler(edit_datetime_handler)],
            EDIT_TIME: [CallbackQueryHandler(edit_datetime_handler)],  # Time handler is part of datetime flow
            EDIT_GAME: [CallbackQueryHandler(edit_game_handler, pattern=r"^game_\w+$")],
            EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_description_handler)],
            EDIT_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_limit_handler)],
        },
        fallbacks=[CallbackQueryHandler(edit_cancel, pattern="^edit_cancel$"),
                   MessageHandler(filters.Regex("^(Отмена|cancel)$"), edit_cancel)],
        persistent=False,
        name="event_edit_conversation",
    )

    rating_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(request_rating, pattern=r"rate_event_\w+_\d+")],
        states={
            RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_rating)],
        },
        fallbacks=[MessageHandler(filters.COMMAND, cancel_creation)],  # Можно добавить более конкретный fallback
        persistent=False,
        name="rating_conversation",
    )

    application.add_handler(conv_handler)
    application.add_handler(edit_conv_handler)  # Регистрируем обработчик редактирования
    application.add_handler(rating_conv_handler)  # Регистрируем обработчик для рейтинга
    application.add_handler(MessageHandler(filters.Regex(r"^👀 Активные события$"), active_events_handler))
    application.add_handler(
        MessageHandler(filters.Regex(r"^⚙️ Мои события$"), my_events))  # Добавляем обработчик для "Мои события"

    application.add_handler(CallbackQueryHandler(join_event, pattern=r"join_\w+"))
    application.add_handler(CallbackQueryHandler(event_details, pattern=r"info_\w+"))

    # Обработчики отмены
    application.add_handler(CallbackQueryHandler(cancel_event, pattern=r"^cancel_event_\w+$"))
    application.add_handler(CallbackQueryHandler(confirm_cancel_event, pattern=r"^confirm_cancel_event_\w+$"))
    application.add_handler(CallbackQueryHandler(do_not_cancel_event, pattern=r"^do_not_cancel_event$"))

    application.add_handler(CommandHandler("my_events", my_events))  # Команда /my_events также будет работать