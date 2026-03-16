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


def shorten_id(id_string: str) -> str:
    """
    Сокращает длинный UUID до короткого хеша (8 символов)
    """
    return hashlib.md5(id_string.encode()).hexdigest()[:8]


async def show_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список разделов (главное меню)"""
    query = update.callback_query
    user = update.effective_user
    
    # Очищаем старые соответствия
    if 'section_map' not in context.bot_data:
        context.bot_data['section_map'] = {}
    
    # Создаем клавиатуру с разделами
    keyboard = []
    
    # Добавляем кнопки разделов
    for section in db.data.sections.values():
        # Создаем короткий ключ
        short_key = shorten_id(section.id)
        # Сохраняем соответствие короткого ключа и реального ID
        context.bot_data['section_map'][short_key] = section.id
        
        callback_data = f"sec_{short_key}"
        logger.info(f"🔧 Создана кнопка раздела: {callback_data} -> {section.name}")
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
    
    logger.info(f"🔍 Поиск раздела с ID: {section_id}")
    section = db.data.sections.get(section_id)
    
    if not section:
        logger.error(f"❌ Раздел не найден: {section_id}")
        await query.edit_message_text("❌ Раздел не найден")
        await show_sections(update, context)
        return
    
    logger.info(f"✅ Раздел найден: {section.name}")
    
    # Очищаем старые соответствия для кнопок
    if 'button_map' not in context.bot_data:
        context.bot_data['button_map'] = {}
    
    # Формируем клавиатуру с кнопками раздела
    keyboard = []
    for button in section.buttons.values():
        # Создаем короткий ключ для кнопки
        short_key = shorten_id(button.id)
        # Сохраняем соответствие
        map_key = f"{shorten_id(section.id)}_{short_key}"
        context.bot_data['button_map'][map_key] = {
            'section_id': section.id,
            'button_id': button.id
        }
        
        callback_data = f"btn_{map_key}"
        keyboard.append([InlineKeyboardButton(
            f"🔘 {button.name}",
            callback_data=callback_data
        )])
    
    # Добавляем кнопку добавления (если пользователь админ)
    user = update.effective_user
    if is_admin(user.id):
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
