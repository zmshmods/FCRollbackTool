import sys
import os
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import setTheme, setThemeColor, Theme
from qframelesswindow import AcrylicWindow, StandardTitleBar
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtCore import Qt

from UIComponents.Personalization import AcrylicEffect
from UIComponents.MainStyles import MainStyles

from Core.Logger import logger
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.ErrorHandler import ErrorHandler

class SteamWindow(AcrylicWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.config_mgr = ConfigManager()
        self.game_mgr = GameManager()
        self.setWindowTitle("Repair Game - Steam")
        self.resize(370, 100)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        AcrylicEffect(self)
        self.center_window()
        
        # Initialize selected game
        self.selected_game = None
        self.validate_game_selection()
        if not self.selected_game:
            self.close()
            return
        
        self.setup_ui()
        self.launch_steam_repair()

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        x = (screen.width() - window_geometry.width()) // 2
        y = (screen.height() - window_geometry.height()) // 2
        self.move(x, y)

    def create_title_bar(self):
        try:
            title_bar = StandardTitleBar(self)
            self.setTitleBar(title_bar)
            title_bar.maxBtn.hide()
            title_bar.minBtn.hide()
            title_bar.setDoubleClickEnabled(False)
            self.title_bar_container = QWidget(self)
            self.title_bar_container.setStyleSheet("background-color: transparent;")
            self.title_bar_container.setFixedHeight(32)
            self.title_bar_container.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            title_bar_layout = QHBoxLayout(self.title_bar_container)
            title_bar_layout.setContentsMargins(10, 0, 10, 0)
            self.title_label = QLabel(self.windowTitle(), self)
            self.title_label.setStyleSheet("color: white; background-color: transparent; font-size: 16px;")
            self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            title_bar_layout.addWidget(self.title_label)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.addWidget(self.title_bar_container)
            separator = QWidget(self)
            separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
            separator.setFixedHeight(1)
            self.main_layout.addWidget(separator)
        except Exception as e:
            ErrorHandler.handleError(f"Error creating title bar: {e}")

    def setup_ui(self):
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 5)
            self.create_title_bar()
            self.create_transparent_container()
            self.main_layout.setSpacing(0)
        except Exception as e:
            ErrorHandler.handleError(f"Error setting up UI: {e}")

    def validate_game_selection(self):
        try:
            selected_game_path = self.config_mgr.getConfigKeySelectedGame()
            if not selected_game_path:
                ErrorHandler.handleError("No selected game path found in config.")
                return

            short_game_name = self.game_mgr.getShortGameName(selected_game_path)
            if not short_game_name:
                ErrorHandler.handleError(f"Could not determine game name from path: {selected_game_path}")
                return

            # Define Steam AppIDs
            SteamAppID = {
                "FC24": 2195250,
                "FC25": 2669320
            }

            if short_game_name not in SteamAppID:
                ErrorHandler.handleError(f"Game '{short_game_name}' is not recognized.")
                return

            self.selected_game = short_game_name
            self.app_id = SteamAppID[short_game_name]
        except Exception as e:
            ErrorHandler.handleError(f"Error validating game selection: {e}")

    def launch_steam_repair(self):
        try:
            if not hasattr(self, 'app_id'):
                ErrorHandler.handleError("No valid AppID found for repair.")
                return
            command = f"steam://validate/{self.app_id}"
            os.system(f"start {command}")
            logger.info(f"Steam launched with repair command for game: {self.selected_game} (AppID: {self.app_id})")
        except Exception as e:
            ErrorHandler.handleError(f"Error launching Steam repair: {e}")
            self.close()

    def create_transparent_container(self):
        try:
            self.transparent_container = QWidget(self)
            self.transparent_container.setStyleSheet("background-color: rgba(0, 0, 0, 0.1);")
            self.transparent_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            layout = QVBoxLayout(self.transparent_container)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            first_row_layout = QHBoxLayout()
            first_row_layout.setAlignment(Qt.AlignLeft)
            icon_label = QLabel(self)
            pixmap = QPixmap("Data/Assets/Icons/ic_fluent_checkmark_circle_24_regular.png")
            if pixmap.isNull():
                logger.warning("Failed to load checkmark icon.")
            icon_label.setPixmap(pixmap)
            icon_label.setStyleSheet("background-color: transparent;")
            icon_label.setFixedSize(20, 20)
            icon_label.setScaledContents(True)
            text_label = QLabel(f"Steam launched with repair command for ({self.selected_game})", self)
            text_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background-color: transparent;")
            text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            first_row_layout.addWidget(icon_label)
            first_row_layout.addWidget(text_label)
            layout.addLayout(first_row_layout)
            second_row_layout = QHBoxLayout()
            second_row_layout.setAlignment(Qt.AlignLeft)
            empty_icon = QLabel(self)
            empty_icon.setFixedSize(20, 20)
            empty_icon.setStyleSheet("background-color: transparent;")
            additional_text = QLabel(
                "It may take some time to repair, you can close this window.",
                self
            )
            additional_text.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 12px; background-color: transparent;")
            additional_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            second_row_layout.addWidget(empty_icon)
            second_row_layout.addWidget(additional_text)
            layout.addLayout(second_row_layout)
            self.main_layout.addWidget(self.transparent_container)
        except Exception as e:
            ErrorHandler.handleError(f"Error creating transparent container: {e}")

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    setTheme(Theme.DARK)
    setThemeColor("#00FF00")
    main_window = SteamWindow()
    main_window.show()
    return app.exec()

if __name__ == "__main__":
    main()