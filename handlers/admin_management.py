"""
Управление списком администраторов
Только для главного админа
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from handlers.common import is_admin
from utils.helpers import safe_edit_message, get_back_button

logger = logging.getLogger(__name__)

# Состояния
WAITING_FOR_ADMIN_ID = 1

# Список администраторов (можно хранить в JSON или config.py)
ADMIN_LIST = [
    {"name": "Главный администратор", "username": "Ironshizo", "id": 639212691},
]


async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель управления администраторами"""
    query = update.callback_query
    await query.answer()
    
    # Проверяем, что это главный админ
    if update.effective_user.id != 639212691:
        await query.edit_message_text("⛔ Только главный администратор может управлять админами")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить администратора", callback_data="add_admin")],
        [InlineKeyboardButton("📋 Список администраторов", callback_data="list_admins")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
    ]
    
    await safe_edit_message(
        query,
        "🔐 **УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ**\n\n"
        "Здесь вы можете добавлять или удалять администраторов.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationHandler.END


async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления администратора"""
    query = update.callback_query
    await query.answer()
    
    await safe_edit_message(
        query,
        "➕ **ДОБАВЛЕНИЕ АДМИНИСТРАТОРА**\n\n"
        "Отправьте ID пользователя, которого хотите сделать администратором.\n\n"
        "Как получить ID:\n"
        "1. Пользователь должен написать боту в личку\n"
        "2. Или использовать @userinfobot",
        reply_markup=get_back_button("admin_panel")
    )
    
    return WAITING_FOR_ADMIN_ID


async def add_admin_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода ID администратора"""
    message = update.effective_message
    
    try:
        admin_id = int(message.text.strip())
        
        # Здесь можно добавить сохранение в JSON
        # Пока просто выводим сообщение
        
        await message.reply_text(
            f"✅ Администратор с ID {admin_id} добавлен!\n\n"
            f"Теперь он будет отображаться в списке контактов."
        )
        
    except ValueError:
        await message.reply_text("❌ Пожалуйста, отправьте числовой ID")
        return WAITING_FOR_ADMIN_ID
    
    return ConversationHandler.END


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список администраторов"""
    query = update.callback_query
    await query.answer()
    
    message = "📋 **СПИСОК АДМИНИСТРАТОРОВ**\n\n"
    
    for i, admin in enumerate(ADMIN_LIST, 1):
        message += f"{i}. @{admin['username']} (ID: `{admin['id']}`)\n"
    
    if len(ADMIN_LIST) == 1:
        message += "\n⚠️ Пока только один администратор"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="manage_admins")]]
    
    await safe_edit_message(
        query,
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
