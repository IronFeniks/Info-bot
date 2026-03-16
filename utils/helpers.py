"""
Вспомогательные функции
"""

import logging
from typing import Optional, Union, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import db

logger = logging.getLogger(__name__)


def get_main_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Создает главное меню со списком разделов"""
    keyboard = []
    
    # Добавляем кнопки разделов
    for section in db.data.sections.values():
        keyboard.append([InlineKeyboardButton(
            f"📁 {section.name}",
            callback_data=f"section_{section.id}"
        )])
    
    # Добавляем функциональные кнопки
    action_buttons = []
    action_buttons.append(InlineKeyboardButton(
        "➕ Добавить инфу",
        callback_data="add_content_start"
    ))
    action_buttons.append(InlineKeyboardButton(
        "🆘 Вызов администратора",
        callback_data="call_admin"
    ))
    keyboard.append(action_buttons)
    
    # Для админа добавляем кнопку управления
    if is_admin:
        keyboard.append([InlineKeyboardButton(
            "🔧 Управление",
            callback_data="admin_panel"
        )])
    
    return InlineKeyboardMarkup(keyboard)


def get_back_button(callback_data: str = "back_to_main") -> InlineKeyboardMarkup:
    """Создает клавиатуру с одной кнопкой 'Назад'"""
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)


async def safe_edit_message(query, text: str, reply_markup=None):
    """Безопасно редактирует сообщение"""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        await query.message.reply_text(text, reply_markup=reply_markup)


async def send_content(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       section_id: str, button_id: str):
    """Отправляет контент кнопки в текущий чат/топик"""
    section = db.data.sections.get(section_id)
    if not section:
        return
    
    button = section.buttons.get(button_id)
    if not button:
        return
    
    chat_id = update.effective_chat.id
    message_thread_id = update.effective_message.message_thread_id
    
    # Формируем подпись
    caption = f"*{button.name}*"
    if button.content.text:
        caption += f"\n\n{button.content.text}"
    
    # Отправляем фото
    for photo in button.content.photos:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo.file_id,
                caption=caption if photo == button.content.photos[0] else None,
                parse_mode="Markdown",
                message_thread_id=message_thread_id
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            # Пробуем восстановить из бэкапа
            if photo.backup:
                new_file_id = await db.restore_from_backup(context, photo.backup)
                if new_file_id:
                    photo.file_id = new_file_id
                    db.save()
                    # Повторяем отправку
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo.file_id,
                        caption=caption if photo == button.content.photos[0] else None,
                        parse_mode="Markdown",
                        message_thread_id=message_thread_id
                    )
    
    # Отправляем видео
    for video in button.content.videos:
        try:
            await context.bot.send_video(
                chat_id=chat_id,
                video=video.file_id,
                caption=caption if not button.content.photos and video == button.content.videos[0] else None,
                parse_mode="Markdown",
                message_thread_id=message_thread_id
            )
        except Exception as e:
            logger.error(f"Ошибка отправки видео: {e}")
            # Пробуем восстановить из бэкапа
            if video.backup:
                new_file_id = await db.restore_from_backup(context, video.backup)
                if new_file_id:
                    video.file_id = new_file_id
                    db.save()
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=video.file_id,
                        caption=caption if not button.content.photos and video == button.content.videos[0] else None,
                        parse_mode="Markdown",
                        message_thread_id=message_thread_id
                    )
    
    # Если нет медиа, отправляем только текст
    if not button.content.photos and not button.content.videos and button.content.text:
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="Markdown",
            message_thread_id=message_thread_id
        )
