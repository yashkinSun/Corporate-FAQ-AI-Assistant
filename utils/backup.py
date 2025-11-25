# utils/backup.py

import os
import shutil
from datetime import datetime
import logging

from config import BACKUP_FOLDER

logger = logging.getLogger(__name__)

def backup_chroma_db(source_folder: str):
    """
    Копирует папку ChromaDB в папку бэкапов, добавляя дату к имени.
    """
    if not os.path.exists(BACKUP_FOLDER):
        os.makedirs(BACKUP_FOLDER)

    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    target_folder = os.path.join(BACKUP_FOLDER, f"chroma_db_backup_{date_str}")
    try:
        shutil.copytree(source_folder, target_folder)
        logger.info(f"ChromaDB backup created at {target_folder}")
    except Exception as e:
        logger.error(f"Error creating ChromaDB backup: {e}")

def backup_env_file(env_path: str = ".env"):
    """
    Копирует .env файл в папку бэкапов с отметкой даты.
    """
    if not os.path.exists(env_path):
        logger.warning(f".env file not found at {env_path}")
        return
    if not os.path.exists(BACKUP_FOLDER):
        os.makedirs(BACKUP_FOLDER)

    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    backup_file = os.path.join(BACKUP_FOLDER, f"env_backup_{date_str}.env")
    try:
        shutil.copy2(env_path, backup_file)
        logger.info(f".env backup created at {backup_file}")
    except Exception as e:
        logger.error(f"Error creating .env backup: {e}")

def restore_chroma_db(backup_folder: str, target_folder: str):
    """
    Восстанавливает хранилище ChromaDB из указанной папки backup_folder
    в target_folder.
    """
    try:
        # Сначала удаляем текущую папку (аккуратно!)
        if os.path.exists(target_folder):
            shutil.rmtree(target_folder)
        # Копируем из бэкапа
        shutil.copytree(backup_folder, target_folder)
        logger.info(f"ChromaDB restored from {backup_folder} to {target_folder}")
    except Exception as e:
        logger.error(f"Error restoring ChromaDB: {e}")
