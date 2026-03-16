"""
Пошаговое добавление контента пользователями
"""

import logging
from typing import Optional, Dict
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database import db
from models import Button, MediaItem
from handlers.common import check_access, is_admin
from utils.validators import validate_section_name, validate_button_name, validate_text
from utils.helpers import get_back_button, safe_edit_message

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    SELECTING_SECTION,
    CREATING_SECTION,
    ENTERING_BUTTON_NAME,
    ENTERING_TEXT,
    ENTERING_PHOTO,
    ENTERING_VIDEO,
    CONFIRMATION
) = range(7)


async def add_content_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления контента"""
    query = update.callback_query
    await query.answer()
    
    if not await check_access(update, context):
        await query.edit_message_text("⛔ Доступ запрещен")
        return ConversationHandler.END
    
    # Сохраняем временные данные
    context.user_data['adding_content'] = {}
    
    # Показываем список разделов для выбора
    keyboard = []
    for section in db.data.sections.values():
        keyboard.append([InlineKeyboardButton(
            f"📁 {section.name}",
            callback_data=f"add_select_section_{section.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        "➕ Создать новый раздел",
        callback_data="add_new_section"
    )])
    
    keyboard.append([InlineKeyboardButton(
        "◀️ Отмена",
        callback_data="back_to_main"
    )])
    
    await safe_edit_message(
        query,
        "🆕 **ДОБАВЛЕНИЕ НОВОЙ ИНФОРМАЦИИ**\n\n"
        "Шаг 1 из 5: Выберите раздел для новой кнопки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return SELECTING_SECTION


async def select_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора существующего раздела"""
    query = update.callback_query
    await query.answer()
    
    section_id = query.data.replace("add_select_section_", "")
    section = db.data.sections.get(section_id)
    
    if not section:
        await query.edit_message_text("❌ Раздел не найден")
        return ConversationHandler.END
    
    context.user_data['adding_content']['section_id'] = section_id
    
    # Запрашиваем название кнопки
    await safe_edit_message(
        query,
        f"🆕 **ДОБАВЛЕНИЕ НОВОЙ ИНФОРМАЦИИ**\n\n"
        f"Выбран раздел: **{section.name}**\n\n"
        f"Шаг 2 из 5: Введите название кнопки.\n"
        f"Название должно быть уникальным в этом разделе.",
        reply_markup=get_back_button("add_content_start")
    )
    
    return ENTERING_BUTTON_NAME


async def new_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание нового раздела"""
    query = update.callback_query
    await query.answer()
    
    await safe_edit_message(
        query,
        "🆕 **СОЗДАНИЕ НОВОГО РАЗДЕЛА**\n\n"
        "Введите название нового раздела:",
        reply_markup=get_back_button("add_content_start")
    )
    
    return CREATING_SECTION


async def create_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода названия нового раздела"""
    message = update.effective_message
    user = update.effective_user
    
    if not message.text:
        await message.reply_text("❌ Пожалуйста, введите текст")
        return CREATING_SECTION
    
    section_name = message.text.strip()
    
    # Валидация
    is_valid, error = validate_section_name(section_name)
    if not is_valid:
        await message.reply_text(f"❌ {error}\n\nПопробуйте еще раз:")
        return CREATING_SECTION
    
    # Создаем новый раздел
    new_section = Section.create(section_name, user.id)
    db.data.sections[new_section.id] = new_section
    db.save()
    
    context.user_data['adding_content']['section_id'] = new_section.id
    
    await message.reply_text(
        f"✅ Раздел **{section_name}** создан!\n\n"
        f"Шаг 2 из 5: Введите название кнопки:",
        parse_mode="Markdown"
    )
    
    return ENTERING_BUTTON_NAME


async def enter_button_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода названия кнопки"""
    message = update.effective_message
    user = update.effective_user
    
    if not message.text:
        await message.reply_text("❌ Пожалуйста, введите текст")
        return ENTERING_BUTTON_NAME
    
    button_name = message.text.strip()
    section_id = context.user_data['adding_content']['section_id']
    
    # Валидация
    is_valid, error = validate_button_name(section_id, button_name)
    if not is_valid:
        await message.reply_text(f"❌ {error}\n\nПопробуйте еще раз:")
        return ENTERING_BUTTON_NAME
    
    # Создаем новую кнопку
    new_button = Button.create(button_name, user.id)
    context.user_data['adding_content']['button'] = new_button
    
    # Переходим к вводу текста
    await message.reply_text(
        f"✅ Название кнопки: **{button_name}**\n\n"
        f"Шаг 3 из 5: Добавьте текст (необязательно).\n"
        f"Просто отправьте текст или нажмите кнопку 'Пропустить'.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭ Пропустить", callback_data="skip_text")
        ]]),
        parse_mode="Markdown"
    )
    
    return ENTERING_TEXT


async def enter_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода текста"""
    message = update.effective_message
    
    if message.text:
        text = message.text.strip()
        is_valid, error = validate_text(text)
        if not is_valid:
            await message.reply_text(f"❌ {error}\n\nПопробуйте еще раз или пропустите:")
            return ENTERING_TEXT
        
        context.user_data['adding_content']['button'].content.text = text
    
    # Переходим к фото
    await message.reply_text(
        "✅ Текст сохранен (если был введен).\n\n"
        "Шаг 4 из 5: Добавьте фото (необязательно).\n"
        "Отправьте фото или нажмите 'Пропустить'.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭ Пропустить", callback_data="skip_photo")
        ]])
    )
    
    return ENTERING_PHOTO


async def skip_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск ввода текста"""
    query = update.callback_query
    await query.answer()
    
    await safe_edit_message(
        query,
        "⏭ Текст пропущен.\n\n"
        "Шаг 4 из 5: Добавьте фото (необязательно).\n"
        "Отправьте фото или нажмите 'Пропустить'.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭ Пропустить", callback_data="skip_photo")
        ]])
    )
    
    return ENTERING_PHOTO


async def enter_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка получения фото"""
    message = update.effective_message
    
    if message.photo:
        # Берем самое большое фото
        photo = message.photo[-1]
        
        # Создаем бэкап
        backup = await db.backup_media(context, photo.file_id, "photo")
        
        # Добавляем фото к кнопке
        media_item = MediaItem(file_id=photo.file_id, backup=backup)
        context.user_data['adding_content']['button'].content.photos.append(media_item)
        
        await message.reply_text(
            "✅ Фото сохранено.\n\n"
            "Шаг 5 из 5: Добавьте видео (необязательно).\n"
            "Отправьте видео или нажмите 'Завершить'.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Завершить", callback_data="finish_adding")
            ]])
        )
        
        return ENTERING_VIDEO
    
    # Если нет фото, просто переходим к видео
    await message.reply_text(
        "Шаг 5 из 5: Добавьте видео (необязательно).\n"
        "Отправьте видео или нажмите 'Завершить'.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Завершить", callback_data="finish_adding")
        ]])
    )
    
    return ENTERING_VIDEO


async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск добавления фото"""
    query = update.callback_query
    await query.answer()
    
    await safe_edit_message(
        query,
        "⏭ Фото пропущено.\n\n"
        "Шаг 5 из 5: Добавьте видео (необязательно).\n"
        "Отправьте видео или нажмите 'Завершить'.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Завершить", callback_data="finish_adding")
        ]])
    )
    
    return ENTERING_VIDEO


async def enter_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка получения видео"""
    message = update.effective_message
    
    if message.video:
        # Создаем бэкап
        backup = await db.backup_media(context, message.video.file_id, "video")
        
        # Добавляем видео к кнопке
        media_item = MediaItem(file_id=message.video.file_id, backup=backup)
        context.user_data['adding_content']['button'].content.videos.append(media_item)
        
        await message.reply_text("✅ Видео сохранено.")
    
    # Завершаем добавление
    return await finish_adding(update, context)


async def finish_adding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение добавления и сохранение"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
        user_id = query.from_user.id
    else:
        message = update.effective_message
        user_id = update.effective_user.id
    
    # Получаем данные
    adding_data = context.user_data.get('adding_content', {})
    button = adding_data.get('button')
    section_id = adding_data.get('section_id')
    
    if not button or not section_id:
        await message.reply_text("❌ Ошибка: данные не найдены")
        return ConversationHandler.END
    
    # Проверяем, что есть хоть какой-то контент
    if button.content.is_empty():
        await message.reply_text(
            "❌ Нельзя создать пустую кнопку. Добавьте хотя бы текст, фото или видео."
        )
        return ENTERING_TEXT
    
    # Сохраняем кнопку
    db.data.sections[section_id].buttons[button.id] = button
    db.save()
    
    # Очищаем временные данные
    context.user_data.pop('adding_content', None)
    
    # Показываем подтверждение
    keyboard = [[
        InlineKeyboardButton("📋 В меню", callback_data="back_to_main"),
        InlineKeyboardButton("➕ Добавить еще", callback_data="add_content_start")
    ]]
    
    await message.reply_text(
        "✅ **ИНФОРМАЦИЯ УСПЕШНО ДОБАВЛЕНА!**\n\n"
        f"Раздел: **{db.data.sections[section_id].name}**\n"
        f"Кнопка: **{button.name}**\n"
        f"Текст: {'✅' if button.content.text else '❌'}\n"
        f"Фото: {len(button.content.photos)} шт.\n"
        f"Видео: {len(button.content.videos)} шт.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END


async def cancel_adding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена добавления"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop('adding_content', None)
    
    await safe_edit_message(
        query,
        "❌ Добавление отменено.",
        reply_markup=get_back_button("back_to_main")
    )
    
    return ConversationHandler.END
