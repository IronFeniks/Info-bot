"""
Обработчики меню и навигации
"""

import logging
import hashlib

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db
from handlers.common import check_access, is_admin
from utils.helpers import safe_edit_message, send_content, get_main_keyboard

logger = logging.getLogger(__name__)


def shorten_callback(prefix: str, section_id: str, button_id: str = None) -> str:
    """
    Сокращает callback_data чтобы не превышать лимит Telegram (64 байта)
    Использует первые 8 символов хеша ID
    """
    if button_id:
        # Для кнопок: button_{short_section}_{short_button}
        short_section = hashlib.md5(section_id.encode()).hexdigest()[:8]
        short_button = hashlib.md5(button_id.encode()).hexdigest()[:8]
        return f"{prefix}_{short_section}_{short_button}"
    else:
        # Для разделов: section_{short_section}
        short_section = hashlib.md5(section_id.encode()).hexdigest()[:8]
        return f"{prefix}_{short_section}"


async def show_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список разделов (главное меню)"""
    query = update.callback_query
    user = update.effective_user
    
    # Создаем клавиатуру с разделами
    keyboard = []
    
    # Добавляем кнопки разделов
    for section in db.data.sections.values():
        callback_data = shorten_callback("section", section.id)
        # Сохраняем соответствие короткого кода и реального ID
        context.bot_data[f"section_{callback_data}"] = section.id
        keyboard.append([InlineKeyboardButton(
            f"📁 {section.name}",
            callback_data=callback_data
        )])
    
    # Добавляем функциональные кнопки
    action_row = []
    action_row.append(InlineKeyboardButton(
        "➕ Добавить инфу",
        callback_data="add_content_start"
    ))
    action_row.append(InlineKeyboardButton(
        "🆘 Вызов администратора",
        callback_data="call_admin"
    ))
    keyboard.append(action_row)
    
    # Для админа добавляем кнопку управления
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton(
            "🔧 Управление",
            callback_data="admin_panel"
        )])
    
    await safe_edit_message(
        query,
        "📋 **Главное меню**\n\nВыберите раздел:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_section(update: Update, context: ContextTypes.DEFAULT_TYPE, section_id: str):
    """Показывает кнопки внутри раздела"""
    query = update.callback_query
    section = db.data.sections.get(section_id)
    
    if not section:
        await query.answer("❌ Раздел не найден")
        await show_sections(update, context)
        return
    
    # Формируем клавиатуру с кнопками раздела
    keyboard = []
    for button in section.buttons.values():
        callback_data = shorten_callback("button", section.id, button.id)
        # Сохраняем соответствие
        context.bot_data[f"button_{callback_data}"] = (section.id, button.id)
        keyboard.append([InlineKeyboardButton(
            f"🔘 {button.name}",
            callback_data=callback_data
        )])
    
    # Добавляем кнопку добавления (если пользователь админ или мы в режиме добавления)
    user = update.effective_user
    if is_admin(user.id) or context.user_data.get('adding_mode'):
        keyboard.append([InlineKeyboardButton(
            "➕ Добавить кнопку в этот раздел",
            callback_data=f"add_in_section_{section.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        "◀️ Назад к разделам",
        callback_data="back_to_main"
    )])
    
    await safe_edit_message(
        query,
        f"📁 **Раздел: {section.name}**\n\nВыберите пункт:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_button_content(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              section_id: str, button_id: str):
    """Показывает контент кнопки"""
    query = update.callback_query
    await query.answer()
    
    section = db.data.sections.get(section_id)
    if not section:
        await query.message.reply_text("❌ Раздел не найден")
        return
    
    button = section.buttons.get(button_id)
    if not button:
        await query.message.reply_text("❌ Кнопка не найдена")
        return
    
    # Отправляем контент
    await send_content(update, context, section_id, button_id)
    
    # Показываем меню раздела
    await show_section(update, context, section_id)


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    await show_sections(update, context)
