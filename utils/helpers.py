"""
Вспомогательные функции
"""

import logging
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
    
    for section in db.data.sections.values():
        keyboard.append([InlineKeyboardButton(
            f"📁 {section.name}",
            callback_data=f"section_{section.id}"
        )])
    
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


def escape_markdown(text: str) -> str:
    """Экранирует специальные символы MarkdownV2"""
    if not text:
        return text
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def safe_edit_message(query, text: str, reply_markup=None, parse_mode: str = "MarkdownV2"):
    """Безопасно редактирует сообщение"""
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        elif "Can't parse entities" in str(e):
            logger.warning(f"Ошибка парсинга Markdown, пробуем без форматирования")
            try:
                await query.edit_message_text(
                    text=text.replace('*', '').replace('_', '').replace('`', ''),
                    reply_markup=reply_markup,
                    parse_mode=None
                )
            except Exception as e2:
                logger.error(f"Не удалось отправить сообщение без форматирования: {e2}")
        else:
            logger.error(f"Ошибка редактирования: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")


async def send_content(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       section_id: str, button_id: str):
    """Отправляет контент кнопки"""
    section = db.data.sections.get(section_id)
    if not section:
        return
    
    button = section.buttons.get(button_id)
    if not button:
        return
    
    chat_id = update.effective_chat.id
    message_thread_id = update.effective_message.message_thread_id
    
    safe_name = escape_markdown(button.name)
    safe_text = escape_markdown(button.content.text) if button.content.text else None
    
    caption = f"*{safe_name}*"
    if safe_text:
        caption += f"\n\n{safe_text}"
    
    # Отправляем фото
    for i, photo in enumerate(button.content.photos):
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo.file_id,
                caption=caption if i == 0 and not button.content.videos else None,
                parse_mode="MarkdownV2",
                message_thread_id=message_thread_id
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo.file_id,
                caption=f"{button.name}\n\n{button.content.text}" if i == 0 else None,
                parse_mode=None,
                message_thread_id=message_thread_id
            )
    
    # Отправляем видео
    for i, video in enumerate(button.content.videos):
        try:
            await context.bot.send_video(
                chat_id=chat_id,
                video=video.file_id,
                caption=caption if not button.content.photos and i == 0 else None,
                parse_mode="MarkdownV2",
                message_thread_id=message_thread_id
            )
        except Exception as e:
            logger.error(f"Ошибка отправки видео: {e}")
            await context.bot.send_video(
                chat_id=chat_id,
                video=video.file_id,
                caption=f"{button.name}\n\n{button.content.text}" if not button.content.photos and i == 0 else None,
                parse_mode=None,
                message_thread_id=message_thread_id
            )
    
    # Если нет медиа, отправляем только текст
    if not button.content.photos and not button.content.videos and button.content.text:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="MarkdownV2",
                message_thread_id=message_thread_id
            )
        except Exception as e:
            logger.error(f"Ошибка отправки текста: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"{button.name}\n\n{button.content.text}",
                parse_mode=None,
                message_thread_id=message_thread_id
            )
