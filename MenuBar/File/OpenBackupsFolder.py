from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from Core.Initializer import AppDataManager, ConfigManager, GameManager, ErrorHandler

def open_backups_path():
    try:
        path = AppDataManager.getBackupsFolder() + "/" + GameManager().getShortGameName(ConfigManager().getConfigKeySelectedGame())
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    except Exception as e:
        ErrorHandler.handleError(f"Error opening Backups folder: {e}")