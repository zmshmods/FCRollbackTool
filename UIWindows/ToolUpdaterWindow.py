import sys
import os
import webbrowser
from datetime import datetime, timezone
import configparser
from datetime import timedelta

from PySide6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QPushButton
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtCore import Qt
from qframelesswindow import AcrylicWindow
from qfluentwidgets import Theme, setTheme, setThemeColor

from UIComponents.Personalization import AcrylicEffect
from UIComponents.Tooltips import apply_tooltip
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar

from Core.Logger import logger
from Core.ToolUpdateManager import ToolUpdateManager
from Core.ConfigManager import AppDataManager
from Core.ErrorHandler import ErrorHandler

WINDOW_TITLE = "FC Rollback Tool - New Update Available!"
WINDOW_SIZE = (920, 620)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/FRICON.png"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = False
REMINDER_INTERVAL_HOURS = 24

class ToolUpdaterWindow(AcrylicWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.tool_update_manager = ToolUpdateManager()
        self.new_version = None
        self.button_manager = ButtonManager(self)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*WINDOW_SIZE)
        self.setWindowModality(Qt.ApplicationModal)
        AcrylicEffect(self)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

    def setup_ui(self) -> None:
        try:
            self._setup_title_bar()
            self._setup_main_container()
            self._setup_buttons()
        except Exception as e:
            ErrorHandler.handleError(f"Error setting up UI: {e}")

    def center_window(self) -> None:
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _setup_title_bar(self) -> None:
        title_bar = TitleBar(
            self,
            title=WINDOW_TITLE,
            icon_path=ICON_PATH,
            spacer_width=SPACER_WIDTH,
            show_max_button=SHOW_MAX_BUTTON,
            show_min_button=SHOW_MIN_BUTTON,
            show_close_button=SHOW_CLOSE_BUTTON,
            bar_height=BAR_HEIGHT
        )
        title_bar.create_title_bar()

    def _setup_main_container(self) -> None:
        self.main_container = QWidget(self, styleSheet="background-color: transparent;", sizePolicy=QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        title_label = QLabel(f"New Release v{self.new_version} (What's Changed?)")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white; background-color: transparent;")
        title_label.setAlignment(Qt.AlignLeft)
        container_layout.addWidget(title_label)
        container_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))
        changelog_container = QWidget(self)
        changelog_layout = QVBoxLayout(changelog_container)
        changelog_layout.setContentsMargins(0, 5, 0, 5)
        changelog_layout.setSpacing(5)
        for line in self.tool_update_manager.getManifestChangelog():
            stripped_line = line.strip()
            if stripped_line.startswith("- *"):
                changelog_label = QLabel(f"Note: {stripped_line[3:].strip()}")
                changelog_label.setStyleSheet("font-size: 14px; color: yellow; background-color: transparent;")
            else:
                changelog_label = QLabel(f"• {stripped_line[1:].strip()}")
                changelog_label.setStyleSheet("font-size: 14px; color: white; background-color: transparent;")
            changelog_label.setWordWrap(True)
            changelog_layout.addWidget(changelog_label)
        container_layout.addWidget(changelog_container)
        container_layout.addStretch()
        self.main_layout.addWidget(self.main_container)

    def _setup_buttons(self) -> None:
        self.main_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))
        button_container = self.button_manager.create_buttons()
        if button_container:
            self.main_layout.addWidget(button_container)
        else:
            self.main_layout.addWidget(QWidget(self))

    def run_check(self) -> bool:
        try:
            if self.tool_update_manager.getMatchingVersion():
                logger.info(f"No new updates available. Current version: v{self.tool_update_manager.getToolVersion()}")
                return False

            latest_version = self.tool_update_manager.getManifestToolVersion()
            if latest_version == "Unknown Version":
                logger.error(f"Failed to checking for updates, skipping update check.")
                return False

            reminder_file = os.path.join(AppDataManager.getDataFolder(), "reminder_timer.ini")
            if os.path.exists(reminder_file):
                config = configparser.ConfigParser()
                config.read(reminder_file)
                if "REMINDERTIMER" in config:
                    last_skipped_version = config["REMINDERTIMER"].get("lastskippedversion", "")
                    last_skip_time = config["REMINDERTIMER"].get("lastskiptime", "")
                    if last_skipped_version == latest_version and last_skip_time:
                        try:
                            last_skip_datetime = datetime.fromisoformat(last_skip_time)
                            if last_skip_datetime.tzinfo is None:
                                last_skip_datetime = last_skip_datetime.replace(tzinfo=timezone.utc)
                            time_diff = datetime.now(timezone.utc) - last_skip_datetime
                            if time_diff < timedelta(hours=REMINDER_INTERVAL_HOURS):
                                logger.debug(f"Update v{latest_version} skipped recently.")
                                return False
                        except ValueError:
                            logger.warning("Invalid reminder timestamp format, proceeding with update check.")

            logger.info(f"New version v{latest_version} available.")
            self.new_version = latest_version
            self.setup_ui()
            self.show()
            return True

        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return False

class ButtonManager:
    def __init__(self, window: "ToolUpdaterWindow"):
        self.window = window
        self.button_container = None
        self.buttons = {}

    def create_buttons(self) -> QWidget:
        try:
            self._init_buttons()
            self._setup_layout()
            self.button_container = QWidget(self.window)
            self.button_container.setLayout(self.button_layout)
            return self.button_container
        except Exception as e:
            ErrorHandler.handleError(f"Error creating buttons: {e}")
            return None

    def remind_me_later(self) -> None:
        try:
            config = configparser.ConfigParser()
            config["REMINDERTIMER"] = {
                "lastskiptime": datetime.now(timezone.utc).isoformat(),
                "lastskippedversion": self.window.new_version
            }
            reminder_file = os.path.join(AppDataManager.getDataFolder(), "reminder_timer.ini")
            with open(reminder_file, "w") as f:
                config.write(f)
            logger.info(f"User chose remind me later for the new version: v{self.window.new_version}")
            self.window.close()
        except Exception as e:
            ErrorHandler.handleError(f"Error saving reminder timer: {e}")
            self.window.close()

    def update_now(self) -> None:
        try:
            url = self.window.tool_update_manager.getDownloadUrl()
            if url:
                webbrowser.open(url)
            sys.exit(0)
        except Exception as e:
            ErrorHandler.handleError(f"Error opening update URL: {e}")
            sys.exit(1)

    def _init_buttons(self) -> None:
        button_configs = {
            "remind_me_later": ("Remind Me Later", self.remind_me_later, "Placeholder"),
            "update_now": ("Update Now", self.update_now, "Placeholder"),
        }
        for name, (text, func, tooltip) in button_configs.items():
            btn = QPushButton(text)
            btn.clicked.connect(func)
            try:
                apply_tooltip(btn, tooltip)
            except KeyError:
                logger.warning(f"Tooltip identifier '{tooltip}' not found, skipping tooltip.")
            self.buttons[name] = btn

    def _setup_layout(self) -> None:
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.buttons["remind_me_later"])
        self.button_layout.addWidget(self.buttons["update_now"])

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = ToolUpdaterWindow()
    if window.run_check():
        sys.exit(app.exec())
    else:
        app.quit()

if __name__ == "__main__":
    main()