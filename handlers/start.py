from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from keyboards.builder import KeyboardBuilder
from database.crud import UserCRUD  # Импортируем UserCRUD для проверки существования пользователя


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Проверяем, есть ли пользователь в нашей базе данных
    user_exists = await UserCRUD.get_user(user_id)

    if not user_exists:
        # Если пользователя нет, предлагаем ему "Начать"
        # Это будет Inline-кнопка, которая при нажатии вызовет handle_start_callback
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать", callback_data="start_command")]
        ])
        await update.message.reply_text(
            "👋 Добро пожаловать! Нажмите 'Начать', чтобы активировать бота и получать уведомления.",
            reply_markup=keyboard
        )
    else:
        # Если пользователь уже зарегистрирован, показываем основное меню
        await update.message.reply_text(
            "👋 Добро пожаловать! Выберите действие:",
            reply_markup=KeyboardBuilder.main_menu()
        )

    # Добавляем пользователя в базу данных (или обновляем last_seen).
    # Это важно делать здесь, чтобы даже если пользователь просто написал /start без кнопки, он был добавлен.
    await UserCRUD.add_user(user_id)


# Новый обработчик для callback_data "start_command" от Inline-кнопки
async def handle_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Отвечаем на callback, чтобы кнопка перестала "крутиться"
    user_id = query.from_user.id

    # Добавляем пользователя в базу данных (или обновляем last_seen)
    await UserCRUD.add_user(user_id)

    # Редактируем сообщение, чтобы убрать кнопку "Начать" и показать основное меню
    await query.edit_message_text(
        "👋 Добро пожаловать! Выберите действие:",
        reply_markup=KeyboardBuilder.main_menu()
    )


def register_handlers(application):
    # CommandHandler для обработки прямого ввода /start
    application.add_handler(CommandHandler("start", start))
    # CallbackQueryHandler для обработки нажатия на Inline-кнопку "Начать"
    application.add_handler(CallbackQueryHandler(handle_start_callback, pattern="^start_command$"))