"""
Вспомогательные функции
"""

import logging
from typing import Optional, Union, List
import hashlib

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import db

logger = logging.getLogger(__name__)


def get_main_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Создает главное меню со списком разделов"""
    keyboard = []
    
    # Добавляем кнопки разделов
    for section in db.data.sections.values():
        # Создаем короткий callback для раздела
        short_section = hashlib.md5(section.id.encode()).hexdigest()[:8]
        callback_data = f"section_{short_section}"
        keyboard.append([InlineKeyboardButton(
            f"📁 {section.name}",
            callback_data=callback_data
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


def get_section_keyboard(section_id: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для раздела"""
    keyboard = []
    section = db.data.sections.get(section_id)
    if section:
        for button in section.buttons.values():
            # Создаем короткий callback для кнопки
            short_section = hashlib.md5(section_id.encode()).hexdigest()[:8]
            short_button = hashlib.md5(button.id.encode()).hexdigest()[:8]
            callback_data = f"button_{short_section}_{short_button}"
            keyboard.append([InlineKeyboardButton(
                f"🔘 {button.name}",
                callback_data=callback_data
            )])
    keyboard.append([InlineKeyboardButton("⬅️ Назад к разделам", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)


def get_back_button(callback_data: str = "back_to_main") -> InlineKeyboardMarkup:
    """Создает клавиатуру с одной кнопкой 'Назад'"""
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)


async def safe_edit_message(query, text: str, reply_markup=None, parse_mode: str = None):
    """
    Безопасно редактирует сообщение, игнорируя ошибку 'Message is not modified'
    
    Args:
        query: CallbackQuery
        text: Новый текст сообщения
        reply_markup: Клавиатура (опционально)
        parse_mode: Режим разметки (Markdown, HTML и т.д.) - ДОБАВЛЕНО
    """
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode  # Теперь поддерживается
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            # Игнорируем эту ошибку
            logger.debug("Сообщение не изменено (это нормально)")
        else:
            # Другие ошибки логируем
            logger.error(f"Ошибка редактирования сообщения: {e}")
            try:
                # Пробуем отправить новое сообщение
                await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception as e2:
                logger.error(f"Не удалось отправить сообщение: {e2}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании: {e}")
        try:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e2:
            logger.error(f"Не удалось отправить сообщение: {e2}")


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
    for i, photo in enumerate(button.content.photos):
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo.file_id,
                caption=caption if i == 0 and not button.content.videos else None,
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
                        caption=caption if i == 0 and not button.content.videos else None,
                        parse_mode="Markdown",
                        message_thread_id=message_thread_id
                    )
    
    # Отправляем видео
    for i, video in enumerate(button.content.videos):
        try:
            await context.bot.send_video(
                chat_id=chat_id,
                video=video.file_id,
                caption=caption if not button.content.photos and i == 0 else None,
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
                        caption=caption if not button.content.photos and i == 0 else None,
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
