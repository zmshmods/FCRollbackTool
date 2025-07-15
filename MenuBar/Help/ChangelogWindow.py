import sys
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QWidget, QSizePolicy
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtCore import Qt
from qframelesswindow import AcrylicWindow
from qfluentwidgets import Theme, setTheme, setThemeColor

from UIComponents.Personalization import AcrylicEffect
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar

from Core.Logger import logger
from Core.ToolUpdateManager import ToolUpdateManager
from Core.ErrorHandler import ErrorHandler

WINDOW_TITLE = "Changelog"
WINDOW_SIZE = (720, 480)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/ic_fluent_code_24_filled.png"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = True

class ChangelogWindow(AcrylicWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.tool_update_manager = ToolUpdateManager()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*WINDOW_SIZE)
        AcrylicEffect(self)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setup_ui()

    def setup_ui(self) -> None:
        try:
            self._setup_title_bar()
            self._setup_main_container()
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
        title_label = QLabel(f"v{self.tool_update_manager.getToolVersion()} Release")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white; background-color: transparent;")
        title_label.setAlignment(Qt.AlignLeft)
        container_layout.addWidget(title_label)
        container_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))
        changelog_container = QWidget(self)
        changelog_layout = QVBoxLayout(changelog_container)
        changelog_layout.setContentsMargins(0, 5, 0, 5)
        changelog_layout.setSpacing(5)
        for line in self.tool_update_manager.getToolChangelog():
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

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = ChangelogWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    main()