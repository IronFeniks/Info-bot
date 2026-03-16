"""
Централизованный обработчик всех callback-запросов
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from handlers.common import check_access
from handlers.menu import (
    show_sections, show_section, show_button_content, back_to_main
)
from handlers.add_content import (
    add_content_start, select_section, new_section, cancel_adding,
    skip_text, skip_photo, finish_adding
)
from handlers.admin_panel import (
    admin_panel, admin_select_section, admin_show_button,
    admin_edit_choice, admin_edit_text, admin_delete_text,
    admin_edit_photo, admin_add_photo, admin_delete_photo,
    admin_delete_all_photos, admin_edit_video, admin_add_video,
    admin_delete_video, admin_delete_all_videos, admin_delete_confirm,
    admin_delete_yes, admin_cancel
)

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик всех callback-запросов"""
    query = update.callback_query
    await query.answer()
    
    # Проверяем доступ
    if not await check_access(update, context):
        await query.edit_message_text("⛔ Доступ запрещен")
        return
    
    data = query.data
    
    # Навигация
    if data == "back_to_main":
        await show_sections(update, context)
    
    # Меню разделов и кнопок (с сокращенными callback)
    elif data.startswith("section_"):
        # Восстанавливаем реальный ID раздела
        section_id = context.bot_data.get(f"section_{data}")
        if section_id:
            await show_section(update, context, section_id)
        else:
            await query.edit_message_text("❌ Раздел не найден")
    
    elif data.startswith("button_"):
        # Восстанавливаем реальные ID
        button_info = context.bot_data.get(f"button_{data}")
        if button_info:
            section_id, button_id = button_info
            await show_button_content(update, context, section_id, button_id)
        else:
            await query.edit_message_text("❌ Кнопка не найдена")
    
    # Добавление контента
    elif data == "add_content_start":
        await add_content_start(update, context)
    
    elif data.startswith("add_select_section_"):
        await select_section(update, context)
    
    elif data == "add_new_section":
        await new_section(update, context)
    
    elif data == "skip_text":
        await skip_text(update, context)
    
    elif data == "skip_photo":
        await skip_photo(update, context)
    
    elif data == "finish_adding":
        await finish_adding(update, context)
    
    elif data == "cancel_adding":
        await cancel_adding(update, context)
    
    # Админ-панель
    elif data == "admin_panel":
        await admin_panel(update, context)
    
    elif data.startswith("admin_section_"):
        await admin_select_section(update, context)
    
    elif data.startswith("admin_button_"):
        await admin_show_button(update, context)
    
    elif data.startswith("admin_edit_"):
        await admin_edit_choice(update, context)
    
    elif data == "admin_edit_text":
        await admin_edit_text(update, context)
    
    elif data == "admin_delete_text":
        await admin_delete_text(update, context)
    
    elif data == "admin_edit_photo":
        await admin_edit_photo(update, context)
    
    elif data == "admin_add_photo":
        await admin_add_photo(update, context)
    
    elif data.startswith("admin_delete_photo_"):
        await admin_delete_photo(update, context)
    
    elif data == "admin_delete_all_photos":
        await admin_delete_all_photos(update, context)
    
    elif data == "admin_edit_video":
        await admin_edit_video(update, context)
    
    elif data == "admin_add_video":
        await admin_add_video(update, context)
    
    elif data.startswith("admin_delete_video_"):
        await admin_delete_video(update, context)
    
    elif data == "admin_delete_all_videos":
        await admin_delete_all_videos(update, context)
    
    elif data.startswith("admin_delete_") and not data.startswith("admin_delete_"):
        await admin_delete_confirm(update, context)
    
    elif data == "admin_delete_yes":
        await admin_delete_yes(update, context)
    
    # Вызов администратора
    elif data == "call_admin":
        await call_admin(update, context)
    
    else:
        logger.warning(f"Неизвестный callback: {data}")
        await query.edit_message_text("❌ Неизвестная команда")


async def call_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик вызова администратора"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    message = f"🆘 **ВЫЗОВ АДМИНИСТРАТОРА**\n\nОт: @{user.username or 'нет юзернейма'} (ID: `{user.id}`)\n\nНапишите ваше сообщение. Оно будет переслано администратору."
    
    # Переходим в режим ожидания сообщения
    context.user_data['waiting_for_admin_call'] = True
    
    await safe_edit_message(
        query,
        message,
        parse_mode="Markdown"
    )
