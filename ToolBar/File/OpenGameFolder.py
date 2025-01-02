import os
import json
from PySide6.QtCore import QDir, QUrl
from PySide6.QtGui import QDesktopServices

class OpenGameFolder:
    CONFIG_FILE_PATH = "config.json" 

    def __init__(self, parent=None):
        self.parent = parent

    def read_config(self):
        if os.path.exists(self.CONFIG_FILE_PATH):
            with open(self.CONFIG_FILE_PATH, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return None
        return None

    def get_game_path(self, selected_game):
        return selected_game

    def open_game_path(self):
        config_data = self.read_config()
        if config_data:
            selected_game = config_data.get("selected_game", "")
            if selected_game:
                game_path = self.get_game_path(selected_game)
                if game_path and os.path.exists(game_path):
                    self.open_folder(game_path)

    def open_folder(self, folder_path):
        if os.path.isdir(folder_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
