"""
Пошаговое добавление контента пользователями
"""

import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database import db
from models import Section, Button, MediaItem
from handlers.common import check_access
from utils.validators import validate_section_name, validate_button_name, validate_text
from utils.helpers import get_back_button, safe_edit_message
from handlers.menu import rebuild_section_map, rebuild_button_map

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    SELECTING_SECTION,
    CREATING_SECTION,
    ENTERING_BUTTON_NAME,
    ENTERING_TEXT,
    ADDING_MEDIA,
    CONFIRMATION
) = range(6)


async def add_content_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления контента"""
    # Проверяем, есть ли query (может быть вызвано не из callback)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        # Если нет query, значит это прямое сообщение
        message = update.effective_message
    
    if not await check_access(update, context):
        await message.reply_text("⛔ Доступ запрещен")
        return ConversationHandler.END
    
    # Сохраняем временные данные
    context.user_data['adding_content'] = {
        'photos': [],  # Список для фото
        'videos': []   # Список для видео
    }
    
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
    
    # Если есть query, редактируем сообщение, иначе отправляем новое
    if update.callback_query:
        await safe_edit_message(
            query,
            "🆕 **ДОБАВЛЕНИЕ НОВОЙ ИНФОРМАЦИИ**\n\n"
            "Шаг 1 из 4: Выберите раздел для новой кнопки:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await message.reply_text(
            "🆕 **ДОБАВЛЕНИЕ НОВОЙ ИНФОРМАЦИИ**\n\n"
            "Шаг 1 из 4: Выберите раздел для новой кнопки:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
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
        f"Шаг 2 из 4: Введите название кнопки.\n"
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
    
    # Обновляем карту разделов
    rebuild_section_map(context)
    logger.info(f"✅ Карта разделов обновлена после создания нового раздела: {section_name}")
    
    context.user_data['adding_content']['section_id'] = new_section.id
    
    await message.reply_text(
        f"✅ Раздел **{section_name}** создан!\n\n"
        f"Шаг 2 из 4: Введите название кнопки:",
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
    context.user_data['adding_content']['button_name'] = button_name
    
    # Переходим к вводу текста
    await message.reply_text(
        f"✅ Название кнопки: **{button_name}**\n\n"
        f"Шаг 3 из 4: Добавьте текст (необязательно).\n"
        f"Просто отправьте текст или нажмите кнопку 'Пропустить'.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭ Пропустить текст", callback_data="skip_text")
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
        await message.reply_text("✅ Текст сохранен!")
    
    # Переходим к добавлению медиа
    await show_media_menu(update, context)
    
    return ADDING_MEDIA


async def skip_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск ввода текста"""
    # Проверяем, есть ли query
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        await safe_edit_message(
            query,
            "⏭ Текст пропущен.",
            reply_markup=None
        )
    else:
        await update.effective_message.reply_text("⏭ Текст пропущен.")
    
    # Переходим к добавлению медиа
    await show_media_menu(update, context)
    
    return ADDING_MEDIA


def get_media_menu_keyboard(context):
    """Создает клавиатуру для меню добавления медиа"""
    keyboard = []
    
    # Показываем текущее количество
    photos_count = len(context.user_data['adding_content'].get('photos', []))
    videos_count = len(context.user_data['adding_content'].get('videos', []))
    
    # Кнопки добавления
    keyboard.append([InlineKeyboardButton("📸 Добавить фото", callback_data="add_photo")])
    keyboard.append([InlineKeyboardButton("🎥 Добавить видео", callback_data="add_video")])
    
    # Кнопка пропуска/завершения
    if photos_count > 0 or videos_count > 0:
        # Если уже есть загруженные файлы - показываем "Завершить"
        keyboard.append([InlineKeyboardButton("✅ Завершить добавление", callback_data="finish_adding")])
    else:
        # Если файлов нет - показываем "Пропустить"
        keyboard.append([InlineKeyboardButton("⏭ Пропустить медиа", callback_data="finish_adding")])
    
    keyboard.append([InlineKeyboardButton("◀️ Отмена", callback_data="cancel_adding")])
    
    return InlineKeyboardMarkup(keyboard)


async def show_media_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню для добавления медиа"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.effective_message
    
    photos_count = len(context.user_data['adding_content'].get('photos', []))
    videos_count = len(context.user_data['adding_content'].get('videos', []))
    
    text = (
        f"📸 **ДОБАВЛЕНИЕ МЕДИА**\n\n"
        f"Кнопка: **{context.user_data['adding_content'].get('button_name', '')}**\n"
        f"Текст: {'✅' if context.user_data['adding_content']['button'].content.text else '❌'}\n\n"
        f"📊 **Загружено:**\n"
        f"• Фото: {photos_count} шт.\n"
        f"• Видео: {videos_count} шт.\n\n"
        f"**Выберите действие:**\n"
        f"• Нажмите 'Добавить фото' чтобы загрузить фото\n"
        f"• Нажмите 'Добавить видео' чтобы загрузить видео\n"
        f"• Нажмите 'Пропустить' если медиа не нужны\n"
        f"• Нажмите 'Завершить' когда закончите загрузку"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_media_menu_keyboard(context),
        parse_mode="Markdown"
    )


async def add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления фото"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['adding_content']['waiting_for'] = 'photo'
    
    await safe_edit_message(
        query,
        "📸 **Режим добавления фото**\n\n"
        "Отправляйте фото по одному.\n"
        "После отправки всех фото нажмите 'Готово'.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Готово", callback_data="back_to_media_menu")
        ]])
    )
    
    return ADDING_MEDIA


async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления видео"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['adding_content']['waiting_for'] = 'video'
    
    await safe_edit_message(
        query,
        "🎥 **Режим добавления видео**\n\n"
        "Отправляйте видео по одному.\n"
        "После отправки всех видео нажмите 'Готово'.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Готово", callback_data="back_to_media_menu")
        ]])
    )
    
    return ADDING_MEDIA


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка получения фото или видео"""
    message = update.effective_message
    waiting_for = context.user_data['adding_content'].get('waiting_for')
    
    if waiting_for == 'photo' and message.photo:
        # Берем самое большое фото
        photo = message.photo[-1]
        
        # Создаем бэкап
        backup = await db.backup_media(context, photo.file_id, "photo")
        
        # Добавляем фото в список
        media_item = MediaItem(file_id=photo.file_id, backup=backup)
        if 'photos' not in context.user_data['adding_content']:
            context.user_data['adding_content']['photos'] = []
        context.user_data['adding_content']['photos'].append(media_item)
        
        await message.reply_text(
            f"✅ Фото {len(context.user_data['adding_content']['photos'])} добавлено!\n"
            f"Можете отправить еще фото или нажмите 'Готово'."
        )
        return ADDING_MEDIA
        
    elif waiting_for == 'video' and message.video:
        # Создаем бэкап
        backup = await db.backup_media(context, message.video.file_id, "video")
        
        # Добавляем видео в список
        media_item = MediaItem(file_id=message.video.file_id, backup=backup)
        if 'videos' not in context.user_data['adding_content']:
            context.user_data['adding_content']['videos'] = []
        context.user_data['adding_content']['videos'].append(media_item)
        
        await message.reply_text(
            f"✅ Видео {len(context.user_data['adding_content']['videos'])} добавлено!\n"
            f"Можете отправить еще видео или нажмите 'Готово'."
        )
        return ADDING_MEDIA
    
    else:
        await message.reply_text(
            "❌ Сейчас режим добавления {}. Пожалуйста, отправьте {} или нажмите 'Готово'."
            .format("фото" if waiting_for == 'photo' else "видео", 
                   "фото" if waiting_for == 'photo' else "видео")
        )
        return ADDING_MEDIA


async def back_to_media_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в меню медиа"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['adding_content']['waiting_for'] = None
    await show_media_menu(update, context)
    
    return ADDING_MEDIA


async def finish_adding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение добавления и сохранение"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
        user_id = query.from_user.id
        user = query.from_user
    else:
        message = update.effective_message
        user_id = update.effective_user.id
        user = update.effective_user
    
    # Получаем данные
    adding_data = context.user_data.get('adding_content', {})
    button = adding_data.get('button')
    section_id = adding_data.get('section_id')
    photos = adding_data.get('photos', [])
    videos = adding_data.get('videos', [])
    
    if not button or not section_id:
        await message.reply_text("❌ Ошибка: данные не найдены")
        return ConversationHandler.END
    
    # Добавляем фото и видео к кнопке
    button.content.photos = photos
    button.content.videos = videos
    
    # Проверяем, что есть хоть какой-то контент
    if button.content.is_empty():
        await message.reply_text(
            "❌ Нельзя создать пустую кнопку. Добавьте хотя бы текст, фото или видео."
        )
        return ADDING_MEDIA
    
    # Сохраняем кнопку
    db.data.sections[section_id].buttons[button.id] = button
    db.save()
    
    # Обновляем карту кнопок
    rebuild_button_map(context)
    logger.info(f"✅ Карта кнопок обновлена после создания новой кнопки: {button.name}")
    
    # ========== ОТПРАВЛЯЕМ ИНФОРМАЦИЮ ТОЛЬКО В ЛИЧКУ АДМИНА ==========
    try:
        from config import BACKUP_CHAT_ID
        
        # Формируем сообщение для админа
        admin_message = f"🆕 **НОВАЯ КНОПКА ДОБАВЛЕНА**\n\n"
        admin_message += f"👤 **От:** @{user.username or 'нет'} (ID: `{user_id}`)\n"
        admin_message += f"📁 **Раздел:** {db.data.sections[section_id].name}\n"
        admin_message += f"🔘 **Кнопка:** {button.name}\n\n"
        admin_message += f"📝 **Текст:**\n{button.content.text or '_текст отсутствует_'}\n\n"
        admin_message += f"🖼 **Фото:** {len(photos)} шт.\n"
        admin_message += f"🎥 **Видео:** {len(videos)} шт."
        
        # Отправляем админу в личку
        await context.bot.send_message(
            chat_id=BACKUP_CHAT_ID,
            text=admin_message,
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ Уведомление админу отправлено в личку для кнопки {button.name}")
        
    except Exception as e:
        logger.error(f"❌ Не удалось уведомить админа: {e}")
    # ================================================================
    
    # Очищаем временные данные
    context.user_data.pop('adding_content', None)
    
    # Показываем подтверждение пользователю
    keyboard = [[
        InlineKeyboardButton("📋 В меню", callback_data="back_to_main"),
        InlineKeyboardButton("➕ Добавить еще", callback_data="add_content_start")
    ]]
    
    await message.reply_text(
        "✅ **ИНФОРМАЦИЯ УСПЕШНО ДОБАВЛЕНА!**\n\n"
        f"Раздел: **{db.data.sections[section_id].name}**\n"
        f"Кнопка: **{button.name}**\n"
        f"Текст: {'✅' if button.content.text else '❌'}\n"
        f"Фото: {len(photos)} шт.\n"
        f"Видео: {len(videos)} шт.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END


async def cancel_adding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена добавления"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        await safe_edit_message(
            query,
            "❌ Добавление отменено.",
            reply_markup=get_back_button("back_to_main")
        )
    else:
        await update.effective_message.reply_text(
            "❌ Добавление отменено.",
            reply_markup=get_back_button("back_to_main")
        )
    
    context.user_data.pop('adding_content', None)
    
    return ConversationHandler.END
