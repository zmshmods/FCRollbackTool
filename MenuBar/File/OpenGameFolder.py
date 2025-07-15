from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from Core.ConfigManager import ConfigManager

def open_game_path():
    path = ConfigManager().getConfigKeySelectedGame()
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
