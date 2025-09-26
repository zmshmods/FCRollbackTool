import sys
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QSizePolicy
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
from PySide6.QtCore import Qt, QEvent
from qfluentwidgets import Theme, setTheme, setThemeColor, ScrollArea

from UIComponents.Personalization import BaseWindow
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar

from Core.Logger import logger
from Core.ToolUpdateManager import ToolUpdateManager, GITHUB_ACC, MAIN_REPO
from Core.ErrorHandler import ErrorHandler

WINDOW_TITLE = "Information"
WINDOW_SIZE = (720, 480)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/ic_fluent_info_24_filled.png"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = True

class HoverLabel(QLabel):
    def __init__(self, text: str, url: str, parent: QWidget = None):
        super().__init__(parent)
        
        self.base_html = f"<a href='{url}' style='color: rgba(255, 255, 255, 0.8); text-decoration: none;'>{text}</a>"
        self.hover_html = f"<a href='{url}' style='color: #FFFFFF; text-decoration: none;'>{text}</a>"
        
        self.setText(self.base_html)
        self.setStyleSheet("font-size: 14px; background-color: transparent;")
        self.setOpenExternalLinks(True)
        
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event: QEvent):
        self.setText(self.hover_html)
        return super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        self.setText(self.base_html)
        return super().leaveEvent(event)
    
class InformationWindow(BaseWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*WINDOW_SIZE)
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
            ErrorHandler.handleError(f"Error setting up UI: {str(e)}")

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
        self.main_container = QWidget(self, styleSheet="background-color: transparent;")
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Header Section
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 15, 20, 20)
        header_layout.setSpacing(15)

        icon_label = QLabel()
        pixmap = QPixmap("Data/Assets/Icons/FRICON.png").scaled(52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        icon_label.setFixedSize(52, 52)
        header_layout.addWidget(icon_label, 0, Qt.AlignTop)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        tool_update_mgr = ToolUpdateManager()
        name_label = QLabel("FC Rollback Tool")
        name_label.setStyleSheet("font-size: 18px; color: white;")
        version_str = tool_update_mgr.getToolVersion()
        build_str = tool_update_mgr.getToolBulidVersion()
        version_label = QLabel(f"Version {version_str} (Build {build_str})")
        version_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.7);")
        ea_disclaimer_label = QLabel("The update files provided by this tool remain the intellectual property of Electronic Arts Inc.")
        ea_disclaimer_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.7);")
        ea_disclaimer_label.setWordWrap(True)

        info_layout.addWidget(name_label)
        info_layout.addWidget(version_label)
        info_layout.addWidget(ea_disclaimer_label)
        info_layout.addStretch()

        header_layout.addLayout(info_layout)
        container_layout.addWidget(header_widget)

        # Main Separator
        container_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))

        # Scrollable Content
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("ScrollArea { border: none; background-color: transparent; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 15) # Add bottom margin only to the main scroll layout
        scroll_layout.setSpacing(0)
        scroll_layout.setAlignment(Qt.AlignTop)

        # --- Acknowledgments Section ---
        ack_widget = QWidget()
        ack_layout = QVBoxLayout(ack_widget)
        ack_layout.setContentsMargins(20, 15, 20, 15)
        ack_layout.setSpacing(8)

        ack_title = QLabel("Acknowledgments")
        ack_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white; margin-bottom: 2px;")
        ack_desc = QLabel("This tool is made possible by the following projects and services:")
        ack_desc.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.7); margin-bottom: 5px;")

        ack_layout.addWidget(ack_title)
        ack_layout.addWidget(ack_desc)
        
        libraries_links = [
            ("PyQt-Fluent-Widgets by zhiyiYo and others", "https://github.com/zhiyiYo/PyQt-Fluent-Widgets"),
            ("MediaFire", "https://www.mediafire.com"),
            ("Aria2", "https://github.com/aria2/aria2"),
            ("UnRAR", "https://www.rarlab.com/rar_add.htm"),
            ("FIFASquadFileDownloader by xAranaktu", "https://github.com/xAranaktu/FIFASquadFileDownloader"),
            ("DepotDownloader", "https://github.com/SteamRE/DepotDownloader"),
        ]
        for text, url in libraries_links:
            link_layout = QHBoxLayout()
            link_layout.setSpacing(5)
            icon_label = QLabel()
            pixmap = QPixmap("Data/Assets/Icons/ic_fluent_link_24_regular.png").scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
            link_label = HoverLabel(text, url)
            link_layout.addWidget(icon_label)
            link_layout.addWidget(link_label)
            link_layout.addStretch()
            ack_layout.addLayout(link_layout)
        
        scroll_layout.addWidget(ack_widget)

        # --- Internal Separator ---
        scroll_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))

        # --- Useful Links Section ---
        useful_links_widget = QWidget()
        useful_links_layout = QVBoxLayout(useful_links_widget)
        useful_links_layout.setContentsMargins(20, 15, 20, 15)
        useful_links_layout.setSpacing(5)
        
        useful_title = QLabel("Useful Links")
        useful_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white; margin-bottom: 2px;")
        useful_desc = QLabel("Links to our pages and communities that you may find useful.")
        useful_desc.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.7); margin-bottom: 5px;")
        
        useful_links_layout.addWidget(useful_title)
        useful_links_layout.addWidget(useful_desc)

        useful_links = [
            ("Patreon: ZMSH Mods", "https://www.patreon.com/zmsh"),
            ("Source Code: FC Rollback Tool", f"https://github.com/{GITHUB_ACC}/{MAIN_REPO}"),
            ("Discord: FC Rollback Tool", "https://discord.com/invite/HBvjk7aTzp"),
            ("Discord: EA FC Modding World", "https://discord.com/invite/fifa-modding-world-fmw-1000239960672182272"),
        ]
        for text, url in useful_links:
            link_layout = QHBoxLayout()
            link_layout.setSpacing(5)
            icon_label = QLabel()
            pixmap = QPixmap("Data/Assets/Icons/ic_fluent_link_24_regular.png").scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
            link_label = HoverLabel(text, url)
            link_layout.addWidget(icon_label)
            link_layout.addWidget(link_label)
            link_layout.addStretch()
            useful_links_layout.addLayout(link_layout)
        
        scroll_layout.addWidget(useful_links_widget)
        scroll_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        container_layout.addWidget(scroll_area)
        container_layout.setStretch(2, 1)
        self.main_layout.addWidget(self.main_container)

def main():
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