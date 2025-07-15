import os
import shutil
from typing import Optional
from Core.Logger import logger
from Core.ErrorHandler import ErrorHandler

class AppDataManager:
    TEMP_ROOT = os.getenv('LOCALAPPDATA')
    TEMP_DIR = os.path.join(TEMP_ROOT, "FC_Rollback_Tool", "Temp")
    DATA_DIR = os.path.join(TEMP_ROOT, "FC_Rollback_Tool", "Data")
    BACKUPS_DIR = os.path.join(TEMP_ROOT, "FC_Rollback_Tool", "Data", "Backups")
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUPS_DIR, exist_ok=True)

    @staticmethod
    def getTempFolder() -> str: return AppDataManager.TEMP_DIR
    @staticmethod
    def getDataFolder() -> str: return AppDataManager.DATA_DIR
    @staticmethod
    def getBackupsFolder() -> str: return AppDataManager.BACKUPS_DIR

    @staticmethod
    def manageTempFolder(clean: bool = False, subfolder: str = None, clean_all: bool = False) -> Optional[str]:
        try:
            if clean_all and os.path.exists(AppDataManager.TEMP_DIR):
                shutil.rmtree(AppDataManager.TEMP_DIR, ignore_errors=True)
                logger.info(f"Temp folder fully cleaned: {AppDataManager.TEMP_DIR}")
            elif clean and subfolder:
                subfolder_path = os.path.join(AppDataManager.TEMP_DIR, subfolder)
                if os.path.exists(subfolder_path):
                    shutil.rmtree(subfolder_path, ignore_errors=True)
                    logger.info(f"Temp subfolder cleaned: {subfolder_path}")
            if not os.path.exists(AppDataManager.TEMP_DIR):
                os.makedirs(AppDataManager.TEMP_DIR, exist_ok=True)
            return AppDataManager.TEMP_DIR
        except Exception as e:
            ErrorHandler.handleError(f"Error handling temp folder: {e}")
            return None