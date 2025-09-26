import sys
import re
import requests
from datetime import datetime
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QWidget
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
from PySide6.QtCore import Qt, QThread, Signal, QObject, QEvent
from qfluentwidgets import Theme, setTheme, setThemeColor, ScrollArea, RoundMenu, Action, FluentIcon

from UIComponents.Personalization import BaseWindow
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.Spinner import LoadingSpinner
from Core.ErrorHandler import ErrorHandler
from Core.Logger import logger
from Core.GameManager import GameManager

# Constants
WINDOW_TITLE = "Patch Notes"
WINDOW_SIZE = (990, 640)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/ic_fluent_fire_24_filled.png"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = True

class PatchNotesFetcher(QObject):
    finished = Signal(dict)

    def __init__(self, game_manager: GameManager, url: str):
        super().__init__()
        self.game_manager = game_manager
        self.url = url

    def run(self):
        patch_data = self.game_manager.fetchPatchNotesData(self.url)
        pixmap = QPixmap()

        if patch_data and (cover_url := patch_data.get("coverUrl")):
            try:
                response = requests.get(cover_url, timeout=10)
                response.raise_for_status()
                pixmap.loadFromData(response.content)
            except Exception as e:
                logger.error(f"Failed to download patch notes image from {cover_url}: {e}")
        
        final_data = patch_data or {}
        final_data['pixmap'] = pixmap
        self.finished.emit(final_data)

class PatchNotesWindow(BaseWindow):
    def __init__(self, game_manager: GameManager, patch_notes_url: str, parent=None):
        super().__init__(parent=parent)
        self.game_manager = game_manager
        self.patch_notes_url = patch_notes_url
        self.thread = None
        self.worker = None
        self._initialize_window()

    def eventFilter(self, obj, event):
        if isinstance(obj, QLabel) and event.type() == QEvent.Type.ContextMenu:
            menu = RoundMenu(parent=obj)
            copy_action = Action(FluentIcon.COPY, 'Copy')
            copy_action.setEnabled(obj.hasSelectedText())
            copy_action.triggered.connect(lambda: QApplication.clipboard().setText(obj.selectedText()))
            menu.addAction(copy_action)
            menu.exec(event.globalPos())
            return True
        return super().eventFilter(obj, event)

    def _initialize_window(self):
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*WINDOW_SIZE)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        try:
            self._setup_ui_base()
            self.show_loading()
            self._start_fetching_data()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to initialize PatchNotesWindow: {e}")
            self._cleanup_thread()
            self.close()

    def _setup_ui_base(self):
        self._setup_title_bar()
        self.main_container = QWidget(self, styleSheet="background-color: transparent;")
        self.main_container_layout = QVBoxLayout(self.main_container)
        self.main_container_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.main_container)

    def center_window(self) -> None:
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _setup_title_bar(self) -> None:
        title_bar = TitleBar(
            self, title=WINDOW_TITLE, icon_path=ICON_PATH, spacer_width=SPACER_WIDTH,
            show_max_button=SHOW_MAX_BUTTON, show_min_button=SHOW_MIN_BUTTON,
            show_close_button=SHOW_CLOSE_BUTTON, bar_height=BAR_HEIGHT
        )
        title_bar.create_title_bar()

    def show_loading(self):
        self.spinner = LoadingSpinner(self.main_container)
        self.fetching_label = QLabel("Loading Patch Notes...", self)
        self.fetching_label.setStyleSheet("font-size: 16px; color: white;")
        
        self.main_container_layout.addStretch(1)
        self.main_container_layout.addWidget(self.spinner, 0, Qt.AlignCenter)
        self.main_container_layout.addWidget(self.fetching_label, 0, Qt.AlignCenter)
        self.main_container_layout.addStretch(1)
        
        self.spinner.start()

    def hide_loading(self):
        if hasattr(self, 'spinner') and self.spinner:
            self.spinner.stop()
            self.spinner.deleteLater()
            self.spinner = None
        if hasattr(self, 'fetching_label') and self.fetching_label:
            self.fetching_label.deleteLater()
            self.fetching_label = None
        
        while self.main_container_layout.count():
            item = self.main_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _start_fetching_data(self):
        self.thread = QThread()
        self.worker = PatchNotesFetcher(self.game_manager, self.patch_notes_url)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_data_fetched)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()

    def _on_data_fetched(self, patch_data: dict):
        self.hide_loading()
        if not patch_data or not patch_data.get("title"):
            error_label = QLabel("Failed to load Patch Notes.\nPlease check your connection and try again.")
            error_label.setStyleSheet("font-size: 16px; color: rgba(255,255,255,0.8);")
            error_label.setAlignment(Qt.AlignCenter)
            self.main_container_layout.addStretch(1)
            self.main_container_layout.addWidget(error_label)
            self.main_container_layout.addStretch(1)
        else:
            self._build_content_ui(patch_data)
        self._cleanup_thread()

    def _build_content_ui(self, patch_data: dict):
        self.main_container_layout.setContentsMargins(0, 0, 0, 0)
        self.main_container_layout.setSpacing(0)
        self.main_container_layout.setAlignment(Qt.AlignTop)

        title = patch_data.get("title")
        description = patch_data.get("description")
        pixmap = patch_data.get("pixmap")
        creation_date_str = patch_data.get("creationDate")
        last_activity_str = patch_data.get("lastActivity")

        if pixmap and not pixmap.isNull():
            image_label = QLabel()
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setStyleSheet("background-color: rgba(0,0,0,0.2);")
            max_width = self.width()
            max_height = 200
            scaled_pixmap = pixmap.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(scaled_pixmap)
            image_label.setFixedHeight(scaled_pixmap.height())
            self.main_container_layout.addWidget(image_label)

        
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(20, 15, 20, 15)
        content_layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        title_label.setWordWrap(True)
        title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title_label.installEventFilter(self)
        content_layout.addWidget(title_label)
        
        def create_date_label(prefix, date_str):
            try:
                utc_date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                local_date_obj = utc_date_obj.astimezone()
                date_text = f"{prefix}: {local_date_obj.strftime('%B %d, %Y at %I:%M %p')}"
                label = QLabel(date_text)
                label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.6);")
                label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                label.installEventFilter(self)
                return label
            except (ValueError, TypeError, AttributeError):
                return None

        if creation_date_str:
            if created_label := create_date_label("Published", creation_date_str):
                content_layout.addWidget(created_label)

        content_layout.addSpacing(10)
        content_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))

        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("ScrollArea { border: none; background-color: transparent; }")
        
        scroll_content_widget = QWidget()
        scroll_content_layout = QVBoxLayout(scroll_content_widget)
        scroll_content_layout.setContentsMargins(0, 10, 10, 0)
        scroll_content_layout.setAlignment(Qt.AlignTop)

        desc_label = QLabel()
        desc_label.setTextFormat(Qt.RichText)
        desc_label.setWordWrap(True)
        desc_label.setText(self._format_description(description))
        desc_label.setOpenExternalLinks(True)
        desc_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        desc_label.installEventFilter(self)
        
        scroll_content_layout.addWidget(desc_label)
        scroll_area.setWidget(scroll_content_widget)
        
        content_layout.addWidget(scroll_area)
        self.main_container_layout.addWidget(content_wrapper)

    def _format_description(self, text: str) -> str:
        html = "<body style='color: rgba(255, 255, 255, 0.9); font-size: 14px;'>"
        in_list = False
        
        lines = text.replace('\\@', '@').split('\n')
        link_regex = r'\[([^\]]+)\]\(([^\s"\'\)]+)(?:[ \t]+["\'].*?["\'])?\)'

        def parse_links(line_content):
            return re.sub(link_regex, r'<a href="\2" style="color: #00BFFF; text-decoration: none;">\1</a>', line_content)

        for line in lines:
            stripped_line = line.strip()
            
            if stripped_line.startswith(('### ', '**')):
                if in_list:
                    html += "</ul>"
                    in_list = False
                
                content = stripped_line.lstrip('#* ').rstrip('*')
                html += f"<p style='font-size: 16px; font-weight: bold; color: #FFFFFF; margin-top: 15px; margin-bottom: 5px;'>{content}</p>"
                continue

            if stripped_line.startswith('- '):
                if not in_list:
                    html += "<ul style='margin-left: -20px;'>"
                    in_list = True
                content = parse_links(stripped_line[2:])
                html += f"<li>{content}</li>"
                continue

            if in_list:
                html += "</ul>"
                in_list = False

            if stripped_line:
                parsed_line = parse_links(stripped_line)
                html += f"<p>{parsed_line}</p>"
    
        if in_list:
            html += "</ul>"
            
        html += "</body>"
        return html

    def closeEvent(self, event):
        self._cleanup_thread()
        super().closeEvent(event)

    def _cleanup_thread(self):
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
        self.thread = None
        self.worker = None

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    
    example_url = "https://raw.githubusercontent.com/zmshmods/FCRollbackToolUpdates/main/Profiles/FC26/TitleUpdatesPatchNotes/1.0.2.json"
    
    window = PatchNotesWindow(GameManager(), example_url)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()