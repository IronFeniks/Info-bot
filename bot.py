#!/usr/bin/env python3
"""
Topic Content Bot - Главный файл запуска
Telegram бот для управления контентом в топиках
"""

import logging
import warnings
from telegram.warnings import PTBUserWarning

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

from config import (
    BOT_TOKEN, BOT_NAME, BOT_VERSION, 
    GROUP_CHAT_ID, TOPIC_PUBLIC_ID, TOPIC_ADMIN_ID, 
    ADMIN_ID, DATA_FILE  # <--- ДОБАВЛЕН DATA_FILE
)
from database import db
from handlers.common import start, help_command, infa_command, backup_command, error_handler
from handlers.callbacks import callback_handler
from handlers.add_content import (
    add_content_start, select_section, new_section, create_section,
    enter_button_name, enter_text, skip_text, enter_photo, skip_photo,
    enter_video, finish_adding, cancel_adding,
    SELECTING_SECTION, CREATING_SECTION, ENTERING_BUTTON_NAME,
    ENTERING_TEXT, ENTERING_PHOTO, ENTERING_VIDEO
)
from handlers.admin_panel import (
    admin_panel, admin_select_section, admin_show_button,
    admin_edit_choice, admin_edit_text, admin_save_text, admin_delete_text,
    admin_edit_photo, admin_add_photo, admin_save_photo, admin_delete_photo,
    admin_delete_all_photos, admin_edit_video, admin_add_video, admin_save_video,
    admin_delete_video, admin_delete_all_videos, admin_delete_confirm,
    admin_delete_yes, admin_cancel,
    ADMIN_SELECTING_SECTION, ADMIN_SELECTING_BUTTON, ADMIN_EDITING_CHOICE,
    ADMIN_EDITING_TEXT, ADMIN_EDITING_PHOTO, ADMIN_EDITING_VIDEO,
    ADMIN_DELETING_CONFIRM
)
from handlers.admin_management import (
    manage_admins, add_admin_start, add_admin_process, list_admins,
    WAITING_FOR_ADMIN_ID
)

# Игнорируем предупреждения PTB
warnings.filterwarnings("ignore", category=PTBUserWarning)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Главная функция запуска бота"""
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ======================== ОБЫЧНЫЕ КОМАНДЫ ========================
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("infa", infa_command))
    application.add_handler(CommandHandler("backup", backup_command))  # Новая команда
    
    # ======================== ДОБАВЛЕНИЕ КОНТЕНТА (Conversation) ========================
    add_content_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_content_start, pattern="^add_content_start$"),
            CallbackQueryHandler(add_content_start, pattern="^add_in_section_")
        ],
        states={
            SELECTING_SECTION: [
                CallbackQueryHandler(select_section, pattern="^add_select_section_"),
                CallbackQueryHandler(new_section, pattern="^add_new_section$"),
                CallbackQueryHandler(cancel_adding, pattern="^back_to_main$")
            ],
            CREATING_SECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_section),
                CallbackQueryHandler(add_content_start, pattern="^add_content_start$")
            ],
            ENTERING_BUTTON_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_button_name),
                CallbackQueryHandler(add_content_start, pattern="^add_content_start$")
            ],
            ENTERING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_text),
                CallbackQueryHandler(skip_text, pattern="^skip_text$"),
                CallbackQueryHandler(add_content_start, pattern="^add_content_start$")
            ],
            ENTERING_PHOTO: [
                MessageHandler(filters.PHOTO, enter_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_photo),
                CallbackQueryHandler(skip_photo, pattern="^skip_photo$"),
                CallbackQueryHandler(add_content_start, pattern="^add_content_start$")
            ],
            ENTERING_VIDEO: [
                MessageHandler(filters.VIDEO, enter_video),
                MessageHandler(filters.PHOTO, enter_video),
                CallbackQueryHandler(finish_adding, pattern="^finish_adding$"),
                CallbackQueryHandler(add_content_start, pattern="^add_content_start$")
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(cancel_adding, pattern="^cancel_adding$")
        ],
        name="add_content_conversation",
        persistent=False
    )
    application.add_handler(add_content_conv)
    
    # ======================== АДМИН-ПАНЕЛЬ (Conversation) ========================
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        states={
            ADMIN_SELECTING_SECTION: [
                CallbackQueryHandler(admin_select_section, pattern="^admin_section_"),
                CallbackQueryHandler(admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(admin_cancel, pattern="^back_to_main$")
            ],
            ADMIN_SELECTING_BUTTON: [
                CallbackQueryHandler(admin_show_button, pattern="^admin_button_"),
                CallbackQueryHandler(admin_edit_choice, pattern="^admin_edit_"),
                CallbackQueryHandler(admin_delete_confirm, pattern="^admin_delete_"),
                CallbackQueryHandler(admin_select_section, pattern="^admin_section_"),
                CallbackQueryHandler(admin_panel, pattern="^admin_panel$")
            ],
            ADMIN_EDITING_CHOICE: [
                CallbackQueryHandler(admin_edit_text, pattern="^admin_edit_text$"),
                CallbackQueryHandler(admin_edit_photo, pattern="^admin_edit_photo$"),
                CallbackQueryHandler(admin_edit_video, pattern="^admin_edit_video$"),
                CallbackQueryHandler(admin_select_section, pattern="^admin_section_")
            ],
            ADMIN_EDITING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_save_text),
                CallbackQueryHandler(admin_delete_text, pattern="^admin_delete_text$"),
                CallbackQueryHandler(admin_edit_choice, pattern="^admin_edit_")
            ],
            ADMIN_EDITING_PHOTO: [
                CallbackQueryHandler(admin_add_photo, pattern="^admin_add_photo$"),
                CallbackQueryHandler(admin_delete_photo, pattern="^admin_delete_photo_"),
                CallbackQueryHandler(admin_delete_all_photos, pattern="^admin_delete_all_photos$"),
                MessageHandler(filters.PHOTO, admin_save_photo),
                CallbackQueryHandler(admin_edit_choice, pattern="^admin_edit_")
            ],
            ADMIN_EDITING_VIDEO: [
                CallbackQueryHandler(admin_add_video, pattern="^admin_add_video$"),
                CallbackQueryHandler(admin_delete_video, pattern="^admin_delete_video_"),
                CallbackQueryHandler(admin_delete_all_videos, pattern="^admin_delete_all_videos$"),
                MessageHandler(filters.VIDEO, admin_save_video),
                CallbackQueryHandler(admin_edit_choice, pattern="^admin_edit_")
            ],
            ADMIN_DELETING_CONFIRM: [
                CallbackQueryHandler(admin_delete_yes, pattern="^admin_delete_yes$"),
                CallbackQueryHandler(admin_select_section, pattern="^admin_section_")
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(admin_cancel, pattern="^back_to_main$")
        ],
        name="admin_conversation",
        persistent=False
    )
    application.add_handler(admin_conv)
    
    # ======================== УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ ========================
    admin_management_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(manage_admins, pattern="^manage_admins$")],
        states={
            WAITING_FOR_ADMIN_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_process),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(admin_panel, pattern="^admin_panel$"),
            CallbackQueryHandler(list_admins, pattern="^list_admins$"),
            CallbackQueryHandler(manage_admins, pattern="^add_admin$")
        ],
        name="admin_management_conversation",
        persistent=False
    )
    application.add_handler(admin_management_conv)
    
    # ======================== ОБЩИЙ ОБРАБОТЧИК CALLBACK ========================
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # ======================== ОБРАБОТЧИК СООБЩЕНИЙ ========================
    async def handle_message_fallback(update: Update, context):
        """Обработчик сообщений, не попавших в другие хендлеры"""
        # Игнорируем все сообщения, не попавшие в диалоги
        pass
    
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO,
        handle_message_fallback
    ))
    
    # ======================== ОБРАБОТЧИК ОШИБОК ========================
    application.add_error_handler(error_handler)
    
    # ======================== ЗАПУСК ========================
    logger.info(f"🤖 {BOT_NAME} v{BOT_VERSION} запускается...")
    logger.info(f"📊 Группа ID: {GROUP_CHAT_ID}")
    logger.info(f"📌 Топик 1 (публичный): {TOPIC_PUBLIC_ID}")
    logger.info(f"📌 Топик 2 (infa): {TOPIC_ADMIN_ID}")
    logger.info(f"👑 Админ ID: {ADMIN_ID}")
    logger.info(f"💾 Данные сохраняются в: {DATA_FILE}")
    logger.info("=" * 40)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
