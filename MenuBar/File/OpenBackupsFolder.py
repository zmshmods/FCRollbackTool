from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from Core.Logger import logger
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.AppDataManager import AppDataManager
from Core.ErrorHandler import ErrorHandler

def open_backups_path():
    try:
        path = AppDataManager.getBackupsFolder() + "/" + GameManager().getSelectedGameId(ConfigManager().getConfigKeySelectedGame())
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    except Exception as e:
        ErrorHandler.handleError(f"Error opening Backups folder: {e}")