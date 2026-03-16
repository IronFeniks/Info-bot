"""
Работа с JSON-хранилищем
Загрузка, сохранение, бэкапы
"""

import json
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime

from telegram import Bot
from telegram.ext import ContextTypes

from config import DATA_FILE, BACKUP_CHAT_ID
from models import BotData, MediaItem, BackupInfo

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с данными"""
    
    def __init__(self):
        self.data = BotData()
        self.load()
    
    def load(self) -> None:
        """Загружает данные из JSON файла"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                self.data = BotData.from_dict(raw_data)
                logger.info(f"✅ Данные загружены из {DATA_FILE}")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки данных: {e}")
                self.data = BotData()
        else:
            logger.info("📁 Файл данных не найден, создана новая структура")
            self.data = BotData()
    
    def save(self) -> None:
        """Сохраняет данные в JSON файл"""
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Данные сохранены в {DATA_FILE}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")
    
    async def backup_media(self, context: ContextTypes.DEFAULT_TYPE, 
                          file_id: str, file_type: str) -> Optional[BackupInfo]:
        """
        Создает бэкап медиа в личке администратора
        Возвращает информацию о бэкапе
        """
        try:
            # Отправляем копию в личку админа
            if file_type == "photo":
                sent_msg = await context.bot.send_photo(
                    chat_id=BACKUP_CHAT_ID,
                    photo=file_id,
                    caption=f"🖼 Бэкап фото от {datetime.now().isoformat()}"
                )
                new_file_id = sent_msg.photo[-1].file_id
            elif file_type == "video":
                sent_msg = await context.bot.send_video(
                    chat_id=BACKUP_CHAT_ID,
                    video=file_id,
                    caption=f"🎥 Бэкап видео от {datetime.now().isoformat()}"
                )
                new_file_id = sent_msg.video.file_id
            else:
                return None
            
            # Создаем информацию о бэкапе
            backup = BackupInfo(
                chat_id=BACKUP_CHAT_ID,
                message_id=sent_msg.message_id,
                file_id=new_file_id
            )
            
            logger.info(f"✅ Создан бэкап {file_type}: message_id={sent_msg.message_id}")
            return backup
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")
            return None
    
    async def restore_from_backup(self, context: ContextTypes.DEFAULT_TYPE,
                                  backup: BackupInfo) -> Optional[str]:
        """
        Восстанавливает file_id из бэкапа
        Используется при перезапуске бота с новым токеном
        """
        try:
            # Копируем сообщение из лички админа обратно в личку
            # (можно копировать куда угодно, главное получить новый file_id)
            new_msg = await context.bot.copy_message(
                chat_id=BACKUP_CHAT_ID,
                from_chat_id=backup.chat_id,
                message_id=backup.message_id
            )
            
            # Получаем новый file_id
            if new_msg.photo:
                new_file_id = new_msg.photo[-1].file_id
            elif new_msg.video:
                new_file_id = new_msg.video.file_id
            else:
                return None
            
            logger.info(f"✅ Восстановлен file_id: {new_file_id[:20]}...")
            return new_file_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления из бэкапа: {e}")
            return None


# Глобальный экземпляр базы данных
db = Database()
