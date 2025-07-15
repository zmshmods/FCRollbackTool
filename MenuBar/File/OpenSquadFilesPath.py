from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager

def open_squad_files_path():
    path = GameManager().getGameSettingsFolderPath(ConfigManager().getConfigKeySelectedGame())
    if path: QDesktopServices.openUrl(QUrl.fromLocalFile(path))