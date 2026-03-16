"""
Функции для валидации данных
"""

import re
from typing import Optional

from database import db
from models import Section


def validate_section_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Проверяет название раздела
    Возвращает (валидно, сообщение_об_ошибке)
    """
    if not name or not name.strip():
        return False, "Название не может быть пустым"
    
    if len(name) > 100:
        return False, "Название слишком длинное (макс. 100 символов)"
    
    # Проверяем на недопустимые символы
    if re.search(r'[<>\[\]{}|\\]', name):
        return False, "Название содержит недопустимые символы"
    
    return True, None


def validate_button_name(section_id: str, name: str, exclude_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """
    Проверяет название кнопки в разделе
    Возвращает (валидно, сообщение_об_ошибке)
    """
    if not name or not name.strip():
        return False, "Название не может быть пустым"
    
    if len(name) > 100:
        return False, "Название слишком длинное (макс. 100 символов)"
    
    # Проверяем уникальность в разделе
    section = db.data.sections.get(section_id)
    if section and not section.is_name_unique(name, exclude_id):
        return False, "Кнопка с таким названием уже существует в этом разделе"
    
    return True, None


def validate_text(text: Optional[str]) -> tuple[bool, Optional[str]]:
    """Проверяет текст"""
    if text and len(text) > 4000:
        return False, "Текст слишком длинный (макс. 4000 символов)"
    return True, None
