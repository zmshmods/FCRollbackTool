import os
import json
from PySide6.QtCore import QDir, QUrl
from PySide6.QtGui import QDesktopServices
class OpenSquadFilesPath:
    CONFIG_FILE_PATH = "config.json" 
    FC25 = "EA SPORTS FC 25" 
    FC24 = "EA SPORTS FC 24"
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
    def get_settings_path(self, selected_game):
        if self.FC25 in selected_game:
            localappdata_path = os.getenv('LOCALAPPDATA')
            if localappdata_path:
                return os.path.join(localappdata_path, self.FC25, "settings")
        elif self.FC24 in selected_game:
            return os.path.join(QDir.homePath(), "Documents", "FC 24", "settings")
        return None
    def open_squad_files_path(self):
        config_data = self.read_config()
        if config_data:
            selected_game = config_data.get("selected_game", "")
            if selected_game:
                settings_path = self.get_settings_path(selected_game)
                if settings_path and os.path.exists(settings_path):
                    self.open_folder(settings_path)
    def open_folder(self, folder_path):
        if os.path.isdir(folder_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))