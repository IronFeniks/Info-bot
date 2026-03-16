"""
Модели данных для бота
Классы, представляющие структуру контента
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


@dataclass
class BackupInfo:
    """Информация о бэкапе медиа в личке админа"""
    chat_id: int
    message_id: int
    file_id: str
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BackupInfo':
        return cls(**data)


@dataclass
class MediaItem:
    """Элемент медиа (фото или видео)"""
    file_id: str
    backup: Optional[BackupInfo] = None
    
    def to_dict(self) -> Dict:
        result = {"file_id": self.file_id}
        if self.backup:
            result["backup"] = self.backup.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MediaItem':
        backup = BackupInfo.from_dict(data["backup"]) if data.get("backup") else None
        return cls(file_id=data["file_id"], backup=backup)


@dataclass
class Content:
    """Контент кнопки (текст + медиа)"""
    text: Optional[str] = None
    photos: List[MediaItem] = field(default_factory=list)
    videos: List[MediaItem] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "photos": [p.to_dict() for p in self.photos],
            "videos": [v.to_dict() for v in self.videos]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Content':
        return cls(
            text=data.get("text"),
            photos=[MediaItem.from_dict(p) for p in data.get("photos", [])],
            videos=[MediaItem.from_dict(v) for v in data.get("videos", [])]
        )
    
    def is_empty(self) -> bool:
        """Проверяет, пустой ли контент"""
        return not self.text and not self.photos and not self.videos


@dataclass
class Button:
    """Кнопка (элемент внутри раздела)"""
    id: str
    name: str
    content: Content
    created_by: int
    created_at: str
    edited_by: Optional[int] = None
    edited_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "content": self.content.to_dict(),
            "created_by": self.created_by,
            "created_at": self.created_at,
            "edited_by": self.edited_by,
            "edited_at": self.edited_at
        }
    
    @classmethod
    def create(cls, name: str, created_by: int) -> 'Button':
        """Создает новую кнопку"""
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            content=Content(),
            created_by=created_by,
            created_at=datetime.now().isoformat()
        )
    
    @classmethod
    def from_dict(cls, button_id: str, data: Dict) -> 'Button':
        return cls(
            id=button_id,
            name=data["name"],
            content=Content.from_dict(data["content"]),
            created_by=data["created_by"],
            created_at=data["created_at"],
            edited_by=data.get("edited_by"),
            edited_at=data.get("edited_at")
        )


@dataclass
class Section:
    """Раздел с кнопками"""
    id: str
    name: str
    created_by: int
    created_at: str
    buttons: Dict[str, Button] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "buttons": {bid: btn.to_dict() for bid, btn in self.buttons.items()}
        }
    
    @classmethod
    def create(cls, name: str, created_by: int) -> 'Section':
        """Создает новый раздел"""
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            created_by=created_by,
            created_at=datetime.now().isoformat()
        )
    
    @classmethod
    def from_dict(cls, section_id: str, data: Dict) -> 'Section':
        section = cls(
            id=section_id,
            name=data["name"],
            created_by=data["created_by"],
            created_at=data["created_at"]
        )
        
        # Загружаем кнопки
        for btn_id, btn_data in data.get("buttons", {}).items():
            section.buttons[btn_id] = Button.from_dict(btn_id, btn_data)
        
        return section
    
    def is_name_unique(self, button_name: str, exclude_id: Optional[str] = None) -> bool:
        """Проверяет уникальность названия кнопки в разделе"""
        for btn_id, btn in self.buttons.items():
            if exclude_id and btn_id == exclude_id:
                continue
            if btn.name.lower() == button_name.lower():
                return False
        return True


@dataclass
class BotData:
    """Главная структура данных бота"""
    sections: Dict[str, Section] = field(default_factory=dict)
    users: Dict[str, Dict] = field(default_factory=dict)  # Кэш пользователей
    
    def to_dict(self) -> Dict:
        return {
            "sections": {sid: sec.to_dict() for sid, sec in self.sections.items()},
            "users": self.users
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BotData':
        bot_data = cls(users=data.get("users", {}))
        
        # Загружаем разделы
        for sec_id, sec_data in data.get("sections", {}).items():
            bot_data.sections[sec_id] = Section.from_dict(sec_id, sec_data)
        
        return bot_data
    
    def find_button_by_name(self, name: str) -> Optional[tuple[str, str, Button]]:
        """
        Ищет кнопку по названию во всех разделах
        Возвращает (section_id, button_id, button)
        """
        name_lower = name.lower()
        for sec_id, section in self.sections.items():
            for btn_id, button in section.buttons.items():
                if button.name.lower() == name_lower:
                    return (sec_id, btn_id, button)
        return None
