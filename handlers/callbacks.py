"""
Централизованный обработчик всех callback-запросов
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from database import db
from handlers.common import check_access
from handlers.menu import (
    show_sections, show_section, show_button_content, back_to_main,
    rebuild_section_map, rebuild_button_map
)
from handlers.add_content import (
    add_content_start, select_section, new_section, cancel_adding,
    skip_text, finish_adding, add_photo, add_video, back_to_media_menu
)
from handlers.admin_panel import (
    admin_panel, admin_select_section, admin_show_button,
    admin_edit_choice, admin_edit_text, admin_delete_text,
    admin_edit_photo, admin_add_photo, admin_delete_photo,
    admin_delete_all_photos, admin_edit_video, admin_add_video,
    admin_delete_video, admin_delete_all_videos, admin_delete_confirm,
    admin_delete_yes, admin_cancel, admin_delete_section_confirm,
    admin_delete_section_yes
)
from utils.helpers import safe_edit_message

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
    logger.info(f"📨 Callback получен: {data}")
    
    # ======================== НАВИГАЦИЯ ========================
    if data == "back_to_main":
        await show_sections(update, context)
    
    # ======================== УДАЛЕНИЕ РАЗДЕЛА ========================
    # Подтверждение удаления раздела (самый высокий приоритет)
    elif data == "admin_delete_section_yes":
        logger.info(f"✅ Подтверждение удаления раздела")
        await admin_delete_section_yes(update, context)
        # После удаления раздела обновляем карты
        rebuild_section_map(context)
        rebuild_button_map(context)
    
    # Запрос на удаление раздела
    elif data.startswith("admin_delete_section_"):
        logger.info(f"🗑 Запрос удаления раздела: {data}")
        await admin_delete_section_confirm(update, context)
    
    # ======================== УДАЛЕНИЕ КНОПКИ ========================
    # Подтверждение удаления кнопки
    elif data == "admin_delete_yes":
        logger.info(f"✅ Подтверждение удаления кнопки")
        await admin_delete_yes(update, context)
        # После удаления кнопки обновляем карту кнопок
        rebuild_button_map(context)
    
    # Запрос на удаление кнопки
    elif data.startswith("admin_delete_") and not any([
        data.startswith("admin_delete_section_"),
        data.startswith("admin_delete_photo_"),
        data.startswith("admin_delete_video_"),
        data.startswith("admin_delete_all_"),
        data == "admin_delete_yes"
    ]):
        logger.info(f"🗑 Запрос удаления кнопки: {data}")
        await admin_delete_confirm(update, context)
    
    # ======================== РЕДАКТИРОВАНИЕ МЕДИА ========================
    elif data.startswith("admin_delete_photo_"):
        await admin_delete_photo(update, context)
    
    elif data == "admin_delete_all_photos":
        await admin_delete_all_photos(update, context)
    
    elif data.startswith("admin_delete_video_"):
        await admin_delete_video(update, context)
    
    elif data == "admin_delete_all_videos":
        await admin_delete_all_videos(update, context)
    
    elif data == "admin_add_photo":
        await admin_add_photo(update, context)
    
    elif data == "admin_add_video":
        await admin_add_video(update, context)
    
    # ======================== МЕНЮ РАЗДЕЛОВ ========================
    elif data.startswith("section_"):
        short_key = data.replace("section_", "")
        
        # ОТЛАДКА: выводим всю карту разделов
        logger.info(f"🔍 Поиск раздела по ключу: {short_key}")
        section_map = context.bot_data.get('section_map', {})
        logger.info(f"📋 Текущая карта разделов: {section_map}")
        
        section_id = section_map.get(short_key)
        
        if section_id:
            logger.info(f"✅ Найден раздел: {section_id}")
            # Проверяем, существует ли раздел в базе
            if section_id in db.data.sections:
                logger.info(f"📁 Открытие раздела: {db.data.sections[section_id].name}")
                await show_section(update, context, section_id)
            else:
                logger.error(f"❌ Раздел {section_id} есть в карте, но нет в базе!")
                # Обновляем карту и пробуем снова
                rebuild_section_map(context)
                await query.edit_message_text("❌ Раздел не найден в базе данных. Попробуйте еще раз.")
        else:
            logger.error(f"❌ Ключ {short_key} не найден в карте")
            logger.info(f"🔄 Пробуем обновить карту...")
            
            # Пробуем обновить карту
            rebuild_section_map(context)
            
            # Пробуем еще раз
            section_id = context.bot_data.get('section_map', {}).get(short_key)
            if section_id:
                logger.info(f"✅ После обновления ключ найден: {section_id}")
                await show_section(update, context, section_id)
            else:
                logger.error(f"❌ Ключ {short_key} все еще не найден после обновления")
                await query.edit_message_text("❌ Раздел не найден. Попробуйте обновить меню через /start")
    
    # ======================== МЕНЮ КНОПОК ========================
    elif data.startswith("button_"):
        map_key = data.replace("button_", "")
        button_info = context.bot_data.get('button_map', {}).get(map_key)
        if button_info:
            section_id = button_info['section_id']
            button_id = button_info['button_id']
            logger.info(f"🔘 Открытие кнопки: {button_id} в разделе {section_id}")
            await show_button_content(update, context, section_id, button_id)
        else:
            logger.error(f"❌ Кнопка не найдена по ключу: {map_key}")
            await query.edit_message_text("❌ Кнопка не найдена")
    
    # ======================== ДОБАВЛЕНИЕ КОНТЕНТА ========================
    elif data == "add_content_start":
        await add_content_start(update, context)
    
    elif data.startswith("add_select_section_"):
        await select_section(update, context)
    
    elif data == "add_new_section":
        await new_section(update, context)
    
    elif data == "skip_text":
        await skip_text(update, context)
    
    elif data == "add_photo":
        await add_photo(update, context)
    
    elif data == "add_video":
        await add_video(update, context)
    
    elif data == "back_to_media_menu":
        await back_to_media_menu(update, context)
    
    elif data == "finish_adding":
        await finish_adding(update, context)
    
    elif data == "cancel_adding":
        await cancel_adding(update, context)
    
    # ======================== АДМИН-ПАНЕЛЬ ========================
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
    
    elif data == "admin_edit_video":
        await admin_edit_video(update, context)
    
    # ======================== УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ ========================
    elif data == "manage_admins":
        from handlers.admin_management import manage_admins
        await manage_admins(update, context)
    
    elif data == "list_admins":
        from handlers.admin_management import list_admins
        await list_admins(update, context)
    
    elif data == "add_admin":
        from handlers.admin_management import add_admin_start
        await add_admin_start(update, context)
    
    # ======================== ВЫЗОВ АДМИНИСТРАТОРА ========================
    elif data == "call_admin":
        await call_admin(update, context)
    
    else:
        logger.warning(f"❌ Неизвестный callback: {data}")
        await query.edit_message_text("❌ Неизвестная команда")


async def call_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик вызова администратора
    Показывает контакты администратора
    """
    query = update.callback_query
    await query.answer()
    
    # Список администраторов
    admins = [
        {"name": "Главный администратор", "username": "Ironshizo", "id": 639212691},
    ]
    
    # Формируем сообщение
    message = "🆘 **СВЯЗЬ С АДМИНИСТРАТОРОМ**\n\n"
    message += "📝 **Напишите администратору, не забудь приложить скрины**\n\n"
    message += "👤 **Контакты:**\n"
    
    for admin in admins:
        message += f"• @{admin['username']}\n"
    
    message += "\n📎 **При обращении указывайте:**\n"
    message += "• Вашу проблему\n"
    message += "• Скриншоты (если есть)\n"
    message += "• Название кнопки или раздела"
    
    await safe_edit_message(
        query,
        message,
        parse_mode="Markdown"
    )
