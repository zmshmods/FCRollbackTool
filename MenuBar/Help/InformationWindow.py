import sys
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QSizePolicy
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
from PySide6.QtCore import Qt
from qframelesswindow import AcrylicWindow
from qfluentwidgets import Theme, setTheme, setThemeColor

from UIComponents.Personalization import AcrylicEffect
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar

from Core.Logger import logger
from Core.ToolUpdateManager import GITHUB_ACC, MAIN_REPO
from Core.ErrorHandler import ErrorHandler

WINDOW_TITLE = "Information"
WINDOW_SIZE = (720, 480)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/ic_fluent_info_24_outlined.png"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = True

class InformationWindow(AcrylicWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*WINDOW_SIZE)
        AcrylicEffect(self)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setup_ui()

    def setup_ui(self) -> None:
        """Set up the main UI components for the InformationWindow."""
        try:
            self._setup_title_bar()
            self._setup_main_container()
        except Exception as e:
            ErrorHandler.handleError(f"Error setting up UI: {str(e)}")

    def center_window(self) -> None:
        """Center the window on the screen."""
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _setup_title_bar(self) -> None:
        """Configure and create the custom title bar."""
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
        """Set up the main content container with sections."""
        self.main_container = QWidget(self, styleSheet="background-color: transparent;")
        self.main_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setAlignment(Qt.AlignTop)

        # Libraries/Services/Tools Used Section
        libraries_label = QLabel("Libraries/Services/Tools Used")
        libraries_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white; background-color: transparent;")
        container_layout.addWidget(libraries_label)
        
        libraries_container = QWidget(self)
        libraries_layout = QVBoxLayout(libraries_container)
        libraries_layout.setContentsMargins(0, 5, 0, 5) 
        libraries_links = [
            ("PyQt-Fluent-Widgets by zhiyiYo and others", "https://github.com/zhiyiYo/PyQt-Fluent-Widgets"),
            ("MediaFire", "https://www.mediafire.com"),
            ("Aria2", "https://github.com/aria2/aria2"),
            ("UnRAR", "https://www.rarlab.com/rar_add.htm"),
            ("FIFASquadFileDownloader by xAranaktu", "https://github.com/xAranaktu/FIFASquadFileDownloader"),
        ]
        for text, url in libraries_links:
            link_layout = QHBoxLayout()
            icon_label = QLabel()
            pixmap = QPixmap("Data/Assets/Icons/ic_fluent_link_24_regular.png").scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
            icon_label.setFixedSize(16, 16)
            icon_label.setStyleSheet("background-color: transparent;")
            link_label = QLabel(f"<a href='{url}' style='color: rgba(255, 255, 255, 0.8); text-decoration: none;'>{text}</a>")
            link_label.setStyleSheet("font-size: 14px; color: white; background-color: transparent;")
            link_label.setOpenExternalLinks(True)
            link_layout.addWidget(icon_label)
            link_label.setAlignment(Qt.AlignVCenter)
            link_layout.addWidget(link_label)
            link_layout.addStretch()
            libraries_layout.addLayout(link_layout)
        container_layout.addWidget(libraries_container)
        
        container_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))

        # Useful Links Section
        useful_label = QLabel("Useful Links")
        useful_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white; background-color: transparent;")
        container_layout.addWidget(useful_label)
        useful_container = QWidget(self)
        useful_layout = QVBoxLayout(useful_container)
        useful_layout.setContentsMargins(0, 5, 0, 5)
        useful_links = [
            ("Patreon: ZMSH Mods", "https://www.patreon.com/zmsh"),
            ("Github: FC Rollback Tool", f"https://github.com/{GITHUB_ACC}/{MAIN_REPO}"),
            ("Discord: EA FC Modding World", "https://discord.com/invite/fifa-modding-world-fmw-1000239960672182272"),
        ]
        for text, url in useful_links:
            link_layout = QHBoxLayout()
            icon_label = QLabel()
            pixmap = QPixmap("Data/Assets/Icons/ic_fluent_link_24_regular.png").scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
            icon_label.setFixedSize(16, 16)
            icon_label.setStyleSheet("background-color: transparent;")
            link_label = QLabel(f"<a href='{url}' style='color: rgba(255, 255, 255, 0.8); text-decoration: none;'>{text}</a>")
            link_label.setStyleSheet("font-size: 14px; color: white; background-color: transparent;")
            link_label.setOpenExternalLinks(True)
            link_layout.addWidget(icon_label)
            link_label.setAlignment(Qt.AlignVCenter)
            link_layout.addWidget(link_label)
            link_layout.addStretch()
            useful_layout.addLayout(link_layout)
        container_layout.addWidget(useful_container)

        container_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))

        # About Section
        title_label = QLabel("About FC Rollback Tool")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white; background-color: transparent;")
        title_label.setAlignment(Qt.AlignLeft)
        container_layout.addWidget(title_label)
        
        about_label = QLabel(
            "A simple tool for managing updates of EA Sports FC games and restoring previous versions."
        )
        about_label.setStyleSheet("font-size: 14px; color: white; background-color: transparent; margin-top: 4px; margin-bottom: 4px;")
        about_label.setWordWrap(True)
        container_layout.addWidget(about_label)
    
        self.main_layout.addWidget(self.main_container)

def main():
    """Main entry point for the InformationWindow application."""
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = InformationWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    main()