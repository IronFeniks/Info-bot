"""
Пошаговое добавление контента пользователями
"""

import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database import db
from models import Section, Button, MediaItem
from handlers.common import check_access
from utils.validators import validate_section_name, validate_button_name, validate_text
from utils.helpers import get_back_button, safe_edit_message
# Импортируем функции перестройки карт
from handlers.menu import rebuild_section_map, rebuild_button_map

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    SELECTING_SECTION,
    CREATING_SECTION,
    ENTERING_BUTTON_NAME,
    ENTERING_TEXT,
    ADDING_MEDIA,
    CONFIRMATION
) = range(6)


async def add_content_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления контента"""
    # Проверяем, есть ли query (может быть вызвано не из callback)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        # Если нет query, значит это прямое сообщение
        message = update.effective_message
    
    if not await check_access(update, context):
        await message.reply_text("⛔ Доступ запрещен")
        return ConversationHandler.END
    
    # Сохраняем временные данные
    context.user_data['adding_content'] = {
        'photos': [],  # Список для фото
        'videos': []   # Список для видео
    }
    
    # Показываем список разделов для выбора
    keyboard = []
    for section in db.data.sections.values():
        keyboard.append([InlineKeyboardButton(
            f"📁 {section.name}",
            callback_data=f"add_select_section_{section.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        "➕ Создать новый раздел",
        callback_data="add_new_section"
    )])
    
    keyboard.append([InlineKeyboardButton(
        "◀️ Отмена",
        callback_data="back_to_main"
    )])
    
    # Если есть query, редактируем сообщение, иначе отправляем новое
    if update.callback_query:
        await safe_edit_message(
            query,
            "🆕 **ДОБАВЛЕНИЕ НОВОЙ ИНФОРМАЦИИ**\n\n"
            "Шаг 1 из 4: Выберите раздел для новой кнопки:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await message.reply_text(
            "🆕 **ДОБАВЛЕНИЕ НОВОЙ ИНФОРМАЦИИ**\n\n"
            "Шаг 1 из 4: Выберите раздел для новой кнопки:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    return SELECTING_SECTION


# ... остальной код без изменений ...
