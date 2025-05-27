from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from database.crud import RatingCRUD, UserCRUD # Импортируем UserCRUD для получения информации о пользователях
from keyboards.builder import KeyboardBuilder # Если понадобится для оценки, но пока не используется


async def top_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем все средние рейтинги из базы данных
    all_ratings = await RatingCRUD.get_all_average_ratings()

    if not all_ratings:
        await update.message.reply_text("Нет данных для формирования рейтинга.")
        return

    message_text = "⭐ **Топ игроков по рейтингу:**\n\n"
    rank = 1
    for player_data in all_ratings:
        user_id = player_data.get("user_id")
        username = player_data.get("username")
        first_name = player_data.get("first_name")
        average_rating = player_data.get("average_rating", 0.0)

        # Формируем имя пользователя
        if username:
            display_name = f"@{username}"
        elif first_name:
            display_name = first_name
        else:
            display_name = f"Пользователь {user_id}" # Запасной вариант

        message_text += f"{rank}. {display_name}: {average_rating:.2f} ⭐\n"
        rank += 1

    await update.message.reply_text(message_text, parse_mode="Markdown")

# Для регистрации обработчика из главного меню
async def top_players_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await top_players(update, context)

def register_handlers(application):
    # CommandHandler для обработки прямой команды /top
    application.add_handler(CommandHandler("top", top_players))
    # MessageHandler для обработки нажатия кнопки "⭐ Топ игроков" из главного меню
    application.add_handler(MessageHandler(filters.Regex(r"^⭐ Топ игроков$"), top_players_menu_button))