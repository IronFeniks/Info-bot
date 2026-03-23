"""
Обработчики меню и навигации
"""

import logging
import hashlib

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db
from handlers.common import check_access, is_admin
from utils.helpers import safe_edit_message, send_content

logger = logging.getLogger(__name__)


def shorten_id(id_string: str) -> str:
    """
    Сокращает длинный UUID до короткого хеша (8 символов)
    """
    return hashlib.md5(id_string.encode()).hexdigest()[:8]


def rebuild_section_map(context):
    """
    Восстанавливает карту соответствий коротких ключей и ID разделов
    """
    if 'section_map' not in context.bot_data:
        context.bot_data['section_map'] = {}
    
    # Очищаем старую карту
    context.bot_data['section_map'].clear()
    
    # Заполняем карту для всех существующих разделов
    for section in db.data.sections.values():
        short_key = shorten_id(section.id)
        context.bot_data['section_map'][short_key] = section.id
        logger.info(f"🔄 Карта разделов: {short_key} -> {section.name} (ID: {section.id})")
    
    logger.info(f"✅ Карта разделов обновлена: {len(context.bot_data['section_map'])} разделов")
    return context.bot_data['section_map']


def rebuild_button_map(context):
    """
    Восстанавливает карту соответствий для кнопок
    """
    if 'button_map' not in context.bot_data:
        context.bot_data['button_map'] = {}
    
    # Очищаем старую карту
    context.bot_data['button_map'].clear()
    
    # Заполняем карту для всех существующих кнопок
    for section in db.data.sections.values():
        short_section = shorten_id(section.id)
        for button in section.buttons.values():
            short_button = shorten_id(button.id)
            map_key = f"{short_section}_{short_button}"
            context.bot_data['button_map'][map_key] = {
                'section_id': section.id,
                'button_id': button.id
            }
            logger.info(f"🔄 Карта кнопок: {map_key} -> {button.name}")
    
    logger.info(f"✅ Карта кнопок обновлена: {len(context.bot_data['button_map'])} кнопок")
    return context.bot_data['button_map']


async def force_rebuild_maps(context):
    """Принудительно перестраивает все карты"""
    rebuild_section_map(context)
    rebuild_button_map(context)
    logger.info("✅ Все карты принудительно перестроены")
    return True


async def show_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список разделов (главное меню)"""
    query = update.callback_query
    user = update.effective_user
    
    # Восстанавливаем карту разделов перед показом
    rebuild_section_map(context)
    
    # Создаем клавиатуру с разделами
    keyboard = []
    
    # Добавляем кнопки разделов
    for section in db.data.sections.values():
        # Создаем короткий ключ (хеш 8 символов)
        short_key = shorten_id(section.id)
        
        callback_data = f"section_{short_key}"
        logger.info(f"🔧 Создана кнопка раздела: {callback_data} -> {section.name} (ID: {section.id})")
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
    
    # Восстанавливаем карту кнопок
    rebuild_button_map(context)
    
    # Формируем клавиатуру с кнопками раздела
    keyboard = []
    for button in section.buttons.values():
        # Создаем короткий ключ для кнопки
        short_section = shorten_id(section.id)
        short_button = shorten_id(button.id)
        map_key = f"{short_section}_{short_button}"
        
        callback_data = f"button_{map_key}"
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
    
    # Создаем кнопки навигации
    short_section = shorten_id(section_id)
    keyboard = [
        [InlineKeyboardButton("◀️ Назад к разделу", callback_data=f"section_{short_section}")],
        [InlineKeyboardButton("🏠 Завершить (в главное меню)", callback_data="back_to_main")]
    ]
    
    # Отправляем сообщение с кнопками
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📌 **Что дальше?**\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
        message_thread_id=update.effective_message.message_thread_id
    )


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    await show_sections(update, context)
