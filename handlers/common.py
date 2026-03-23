"""
Общие обработчики
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import (
    ADMIN_ID, GROUP_CHAT_ID, TOPIC_PUBLIC_ID, TOPIC_ADMIN_ID,
    WELCOME_MESSAGE, HELP_MESSAGE, BOT_NAME
)
from database import db
from utils.helpers import get_main_keyboard

logger = logging.getLogger(__name__)


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверяет доступ пользователя к боту в текущем топике
    """
    message = update.effective_message
    if not message:
        return False
    
    if message.chat_id != GROUP_CHAT_ID:
        return False
    
    message_thread_id = message.message_thread_id
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        return message_thread_id in (TOPIC_PUBLIC_ID, TOPIC_ADMIN_ID)
    
    return message_thread_id == TOPIC_PUBLIC_ID


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start
    Работает ТОЛЬКО в публичном топике (ID: 18)
    """
    message = update.effective_message
    
    # Проверяем, что сообщение из публичного топика
    if not message or message.message_thread_id != TOPIC_PUBLIC_ID:
        return
    
    if not await check_access(update, context):
        return
    
    user = update.effective_user
    admin_status = is_admin(user.id)
    
    await message.reply_text(
        WELCOME_MESSAGE.format(name=BOT_NAME),
        reply_markup=get_main_keyboard(admin_status),
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    message = update.effective_message
    
    if not message or message.message_thread_id != TOPIC_PUBLIC_ID:
        return
    
    if not await check_access(update, context):
        return
    
    await message.reply_text(
        HELP_MESSAGE,
        parse_mode="Markdown"
    )


async def infa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /infa - только для администратора в Топике 2
    Формат: /infa Название кнопки
    """
    message = update.effective_message
    
    # Проверяем, что команда вызвана в Топике 2
    if not message or message.message_thread_id != TOPIC_ADMIN_ID:
        return
    
    if not await check_access(update, context):
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await message.reply_text("⛔ Эта команда только для администратора.")
        return
    
    args = context.args
    if not args:
        await message.reply_text(
            "❌ Использование: /infa Название кнопки\n\n"
            "Пример: /infa Борщ"
        )
        return
    
    button_name = " ".join(args)
    logger.info(f"🔍 Поиск кнопки по названию: '{button_name}'")
    
    from handlers.menu import rebuild_button_map
    rebuild_button_map(context)
    
    result = db.data.find_button_by_name(button_name)
    
    if not result:
        button_name_clean = button_name.strip().lower()
        for section in db.data.sections.values():
            for btn_id, button in section.buttons.items():
                if button.name.strip().lower() == button_name_clean:
                    result = (section.id, btn_id, button)
                    break
            if result:
                break
    
    if not result:
        await message.reply_text(f"❌ Кнопка '{button_name}' не найдена.")
        return
    
    section_id, button_id, button = result
    
    from utils.helpers import send_content
    await send_content(update, context, section_id, button_id)


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /backup - отправляет копию базы данных админу
    """
    message = update.effective_message
    
    if not message or message.message_thread_id != TOPIC_ADMIN_ID:
        return
    
    if not await check_access(update, context):
        return
    
    if not is_admin(update.effective_user.id):
        await message.reply_text("⛔ Только для администратора")
        return
    
    await message.reply_text("🔄 Создание бэкапа...")
    success = await db.auto_backup(context)
    
    if success:
        await message.reply_text("✅ Бэкап отправлен в личные сообщения")
    else:
        await message.reply_text("❌ Ошибка создания бэкапа")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"❌ Ошибка: {context.error}", exc_info=context.error)
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла внутренняя ошибка. Администратор уже уведомлен."
            )
    except:
        pass
