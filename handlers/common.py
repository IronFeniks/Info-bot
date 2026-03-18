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
from handlers.menu import rebuild_button_map

logger = logging.getLogger(__name__)


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверяет доступ пользователя к боту в текущем топике
    """
    message = update.effective_message
    if not message:
        return False
    
    # Логируем ВСЕ входящие сообщения для отладки
    user = update.effective_user
    chat = update.effective_chat
    
    logger.info(f"📨 Входящее сообщение: chat_id={message.chat_id}, "
                f"chat_type={chat.type if chat else 'unknown'}, "
                f"thread_id={message.message_thread_id}, "
                f"user_id={user.id if user else 'None'}, "
                f"username=@{user.username if user and user.username else 'None'}, "
                f"text={message.text if message.text else 'non-text'}")
    
    # Проверяем, что сообщение из нужной группы
    if message.chat_id != GROUP_CHAT_ID:
        logger.warning(f"Попытка использования из чата {message.chat_id}")
        return False
    
    message_thread_id = message.message_thread_id
    user_id = update.effective_user.id
    
    # ОТЛАДКА: выводим значения
    logger.info(f"🔍 Проверка доступа: chat={message.chat_id}, topic={message_thread_id}, "
                f"PUBLIC={TOPIC_PUBLIC_ID}, ADMIN={TOPIC_ADMIN_ID}")
    
    # Для администратора разрешены оба топика
    if user_id == ADMIN_ID:
        if message_thread_id in (TOPIC_PUBLIC_ID, TOPIC_ADMIN_ID):
            logger.info(f"✅ Доступ разрешен админу в топике {message_thread_id}")
            return True
        else:
            logger.warning(f"Админ попытался использовать топик {message_thread_id}")
            return False
    
    # Для обычных пользователей только публичный топик
    if message_thread_id == TOPIC_PUBLIC_ID:
        logger.info(f"✅ Доступ разрешен пользователю в публичном топике")
        return True
    else:
        logger.warning(f"Пользователь {user_id} попытался использовать топик {message_thread_id}")
        return False


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    if not await check_access(update, context):
        await update.message.reply_text(
            "⛔ Доступ запрещен. Бот работает только в определенных топиках."
        )
        return
    
    user = update.effective_user
    admin_status = is_admin(user.id)
    
    await update.message.reply_text(
        WELCOME_MESSAGE.format(name=BOT_NAME),
        reply_markup=get_main_keyboard(admin_status),
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    if not await check_access(update, context):
        return
    
    await update.message.reply_text(
        HELP_MESSAGE,
        parse_mode="Markdown"
    )


async def infa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /infa - только для администратора в Топике 2
    Формат: /infa Название кнопки
    """
    if not await check_access(update, context):
        return
    
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Эта команда только для администратора.")
        return
    
    # Проверяем, что команда вызвана в Топике 2
    if update.effective_message.message_thread_id != TOPIC_ADMIN_ID:
        await update.message.reply_text("⛔ Команда /infa работает только во втором топике.")
        return
    
    # Получаем название кнопки из аргументов
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Использование: /infa Название кнопки\n\n"
            "Пример: /infa Борщ"
        )
        return
    
    button_name = " ".join(args)
    logger.info(f"🔍 Поиск кнопки по названию: '{button_name}'")
    
    # Принудительно перестраиваем карту кнопок для актуальности данных
    rebuild_button_map(context)
    
    # Ищем кнопку по названию
    result = db.data.find_button_by_name(button_name)
    
    if not result:
        # Пробуем искать без учета регистра и лишних пробелов
        button_name_clean = button_name.strip().lower()
        for section in db.data.sections.values():
            for btn_id, button in section.buttons.items():
                if button.name.strip().lower() == button_name_clean:
                    result = (section.id, btn_id, button)
                    logger.info(f"✅ Найдено по точному совпадению без учета регистра: {button.name}")
                    break
            if result:
                break
    
    if not result:
        # Для отладки выводим все доступные кнопки
        logger.info("📋 Все доступные кнопки в базе:")
        for section in db.data.sections.values():
            for button in section.buttons.values():
                logger.info(f"  • {button.name} (ID: {button.id})")
        
        await update.message.reply_text(f"❌ Кнопка '{button_name}' не найдена.")
        return
    
    section_id, button_id, button = result
    logger.info(f"✅ Найдена кнопка: {button.name} в разделе {db.data.sections[section_id].name}")
    
    # Отправляем контент в текущий топик (Топик 2)
    from utils.helpers import send_content
    await send_content(update, context, section_id, button_id)


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /backup - отправляет копию базы данных админу
    """
    if not await check_access(update, context):
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только для администратора")
        return
    
    await update.message.reply_text("🔄 Создание бэкапа...")
    success = await db.auto_backup(context)
    
    if success:
        await update.message.reply_text("✅ Бэкап отправлен в личные сообщения")
    else:
        await update.message.reply_text("❌ Ошибка создания бэкапа")


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
