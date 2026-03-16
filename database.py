"""
Работа с JSON-хранилищем
"""

import json
import logging
import os
from typing import Optional
from datetime import datetime

from telegram.error import Forbidden
from telegram.ext import ContextTypes

from config import DATA_FILE, BACKUP_CHAT_ID, GROUP_CHAT_ID, TOPIC_ADMIN_ID
from models import BotData, MediaItem, BackupInfo

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с данными"""
    
    def __init__(self):
        """Инициализация базы данных"""
        self.data = BotData()
        self.data_file = DATA_FILE
        self._ensure_file_exists()
        self.load()
    
    def _ensure_file_exists(self):
        """Проверяет существование файла и создает его при необходимости"""
        if not os.path.exists(self.data_file):
            try:
                # Создаем папку, если нужно
                os.makedirs(os.path.dirname(os.path.abspath(self.data_file)), exist_ok=True)
                
                # Создаем файл с пустой структурой
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump({"sections": {}, "users": {}}, f, ensure_ascii=False, indent=2)
                logger.info(f"✅ Создан новый файл данных: {self.data_file}")
            except Exception as e:
                logger.error(f"❌ Ошибка создания файла данных: {e}")
    
    def load(self) -> None:
        """Загружает данные из JSON"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                self.data = BotData.from_dict(raw_data)
                logger.info(f"✅ Данные загружены из {self.data_file}")
                logger.info(f"📊 Статистика: {len(self.data.sections)} разделов, "
                          f"{sum(len(s.buttons) for s in self.data.sections.values())} кнопок")
            else:
                logger.warning(f"📁 Файл {self.data_file} не найден, создаем новый")
                self._ensure_file_exists()
                self.data = BotData()
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных: {e}")
            self.data = BotData()
    
    def save(self) -> None:
        """Сохраняет данные в JSON"""
        try:
            # Создаем резервную копию перед сохранением
            if os.path.exists(self.data_file):
                backup_file = f"{self.data_file}.backup"
                try:
                    os.replace(self.data_file, backup_file)
                except:
                    pass
            
            # Сохраняем новые данные
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Данные сохранены в {self.data_file}")
            
            # Удаляем старый бэкап
            try:
                if os.path.exists(f"{self.data_file}.backup"):
                    os.remove(f"{self.data_file}.backup")
            except:
                pass
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")
            # Пробуем восстановить из бэкапа
            if os.path.exists(f"{self.data_file}.backup"):
                try:
                    os.replace(f"{self.data_file}.backup", self.data_file)
                    logger.info("✅ Данные восстановлены из бэкапа")
                except:
                    pass
    
    def get_stats(self) -> dict:
        """Возвращает статистику базы данных"""
        sections_count = len(self.data.sections)
        buttons_count = sum(len(s.buttons) for s in self.data.sections.values())
        photos_count = 0
        videos_count = 0
        
        for section in self.data.sections.values():
            for button in section.buttons.values():
                photos_count += len(button.content.photos)
                videos_count += len(button.content.videos)
        
        return {
            "sections": sections_count,
            "buttons": buttons_count,
            "photos": photos_count,
            "videos": videos_count
        }
    
    async def backup_media(self, context: ContextTypes.DEFAULT_TYPE, 
                          file_id: str, file_type: str) -> Optional[BackupInfo]:
        """
        Создает бэкап медиа в личке администратора
        Возвращает информацию о бэкапе или None в случае ошибки
        """
        try:
            # Пробуем отправить бэкап
            if file_type == "photo":
                sent_msg = await context.bot.send_photo(
                    chat_id=BACKUP_CHAT_ID,
                    photo=file_id,
                    caption=f"🖼 Бэкап фото от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                new_file_id = sent_msg.photo[-1].file_id
                logger.info(f"✅ Создан бэкап фото: message_id={sent_msg.message_id}")
                
            elif file_type == "video":
                sent_msg = await context.bot.send_video(
                    chat_id=BACKUP_CHAT_ID,
                    video=file_id,
                    caption=f"🎥 Бэкап видео от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                new_file_id = sent_msg.video.file_id
                logger.info(f"✅ Создан бэкап видео: message_id={sent_msg.message_id}")
            else:
                return None
            
            backup = BackupInfo(
                chat_id=BACKUP_CHAT_ID,
                message_id=sent_msg.message_id,
                file_id=new_file_id
            )
            
            return backup
            
        except Forbidden as e:
            # Специфичная ошибка - бот не может инициировать диалог
            logger.error(f"❌ Бот не может отправить сообщение администратору. "
                        f"Администратор (ID: {BACKUP_CHAT_ID}) должен написать боту первый: /start")
            
            # Пытаемся уведомить в группу (только один раз)
            try:
                if not hasattr(context.bot_data, '_backup_warning_sent'):
                    await context.bot.send_message(
                        chat_id=GROUP_CHAT_ID,
                        message_thread_id=TOPIC_ADMIN_ID,
                        text=f"⚠️ **Внимание!**\n\n"
                             f"Бот не может создать бэкап в личке администратора.\n"
                             f"Администратор должен написать боту в личные сообщения: @{context.bot.username}\n\n"
                             f"Команда: /start",
                        parse_mode="Markdown"
                    )
                    context.bot_data['_backup_warning_sent'] = True
            except:
                pass
            
            return None
            
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
            new_msg = await context.bot.copy_message(
                chat_id=BACKUP_CHAT_ID,
                from_chat_id=backup.chat_id,
                message_id=backup.message_id
            )
            
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
    
    def export_to_json(self) -> str:
        """Экспортирует данные в JSON строку"""
        return json.dumps(self.data.to_dict(), ensure_ascii=False, indent=2)
    
    def import_from_json(self, json_str: str) -> bool:
        """Импортирует данные из JSON строки"""
        try:
            raw_data = json.loads(json_str)
            self.data = BotData.from_dict(raw_data)
            self.save()
            logger.info("✅ Данные импортированы успешно")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка импорта данных: {e}")
            return False


# Глобальный экземпляр базы данных
db = Database()
