import os
import sys
from typing import Optional
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QFileSystemModel, QStackedLayout,
    QHeaderView, QAbstractItemView, QPushButton, QSizePolicy, QTableWidgetItem
)
from PySide6.QtCore import Qt, QSize, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from qframelesswindow import AcrylicWindow
from qfluentwidgets import TableWidget, Theme, setTheme, setThemeColor

from Core.Initializer import ConfigManager, GameManager, AppDataManager, ErrorHandler
from Core.Logger import logger
from UIComponents.Spinner import LoadingSpinner
from UIComponents.Tooltips import apply_tooltip
from UIComponents.Personalization import AcrylicEffect
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar

WINDOW_TITLE_SELECT_GAME = "FC Rollback Tool - Select Game"
WINDOW_TITLE_ENTRY = "FC Rollback Tool - Entry Point"
WINDOW_SIZE = (500, 300)
THEME_COLOR = "#00FF00"
APP_ICON_PATH = "Data/Assets/Icons/FRICON.png"
SPACER_WIDTH = 150
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = True

class GameProcessingThread(QThread):
    status_update = Signal(list)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, path: str, config_mgr: ConfigManager, game_mgr: GameManager):
        super().__init__()
        self.path, self.config_mgr, self.game_mgr = path, config_mgr, game_mgr
        self.app_data_manager = AppDataManager()

    def run(self):
        try:
            content = self.game_mgr.loadGameContent(self.path, emit_status=self.status_update.emit)
            if not content:
                return
            if not self.game_mgr.validateAndUpdateGameExeSHA1(self.path, self.config_mgr):
                self.error.emit("Failed to validate the game executable.")
                return
            self.config_mgr.setConfigKeySelectedGame(self.path)
            self.finished.emit(content)
        except Exception as e:
            self.error.emit(f"Error processing game:\n{e}")

class SelectGameWindow(AcrylicWindow):
    def __init__(self, parent: Optional[QWidget] = None, ignore_selected_game: bool = False):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.game_manager = GameManager()
        self.button_manager = ButtonManager(self)
        self.ignore_selected_game = ignore_selected_game
        self.has_valid_selected_game = False
        self.selected_game_path = None

        self.setWindowTitle(WINDOW_TITLE_SELECT_GAME)
        self.resize(*WINDOW_SIZE)
        AcrylicEffect(self)
        self.center_window()

        # Setup spinner container for loading states
        self.spinner_container = QWidget(self, styleSheet="background-color: transparent;")
        layout = QVBoxLayout(self.spinner_container)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self.spinner = LoadingSpinner(self)
        self.spinner.setStyleSheet("background-color: transparent;")
        self.status_label = QLabel("", self, styleSheet="font-size: 14px; background-color: transparent;", alignment=Qt.AlignCenter)
        layout.addWidget(self.spinner, alignment=Qt.AlignCenter)
        layout.addWidget(self.status_label, alignment=Qt.AlignCenter)

        if not self.ignore_selected_game:
            self.selected_game_path = self.config_manager.getConfigKeySelectedGame()
            self.has_valid_selected_game = self.selected_game_path and os.path.exists(self.selected_game_path)

        if self.has_valid_selected_game:
            self.setWindowTitle(WINDOW_TITLE_ENTRY)
            self._setup_entry_point_ui()
            self._handle_entry_point()
        else:
            self._initialize_ui()

    def _initialize_ui(self) -> None:
        self._clear_layout()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 5, 0, 0)
        self.main_layout.setSpacing(0)
        self.interface_container = QWidget(self)
        self.interface_layout = QVBoxLayout(self.interface_container)
        self.interface_layout.setContentsMargins(0, 0, 0, 0)
        self.interface_layout.setSpacing(0)
        self.setup_ui()

    def _setup_entry_point_ui(self) -> None:
        self._clear_layout()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 5, 0, 0)
        self.main_layout.setSpacing(0)
        self.interface_container = QWidget(self)
        self.interface_layout = QVBoxLayout(self.interface_container)
        self.interface_layout.setContentsMargins(0, 0, 0, 0)
        self.interface_layout.setSpacing(0)
        self._setup_title_bar()
        self.interface_layout.addWidget(self.spinner_container)
        self.main_layout.addWidget(self.interface_container)

    def _handle_entry_point(self) -> None:
        """Start processing the selected game in a separate thread."""
        self.thread = GameProcessingThread(self.selected_game_path, self.config_manager, self.game_manager)
        self.thread.status_update.connect(self._update_status)
        self.thread.finished.connect(self._on_entry_point_finished)
        self.thread.error.connect(self._on_entry_point_error)
        self.thread.start()

    @Slot(list)
    def _update_status(self, message_parts: list) -> None:
        html_text = "".join(f'<span style="color:{color}">{text}</span>' for text, color in message_parts)
        self.status_label.setText(html_text)

    @Slot(dict)
    def _on_entry_point_finished(self, content: dict) -> None:
        if not content:
            ErrorHandler.handleError("Failed to load game content. Please try again.")
            self.has_valid_selected_game = False
            self.config_manager.resetSelectedGame()
            self._reset_ui()
            return
        from Main import MainWindow
        self.main_window = MainWindow(self.config_manager, self.game_manager, content)
        self.main_window.show()
        self.close()

    @Slot(str)
    def _on_entry_point_error(self, msg: str) -> None:
        ErrorHandler.handleError(msg)
        self.has_valid_selected_game = False
        self.config_manager.resetSelectedGame()
        self._reset_ui()

    def _clear_layout(self) -> None:
        if self.layout() is not None:
            old_layout = self.layout()
            while old_layout.count():
                child = old_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            old_layout.deleteLater()
            self.setLayout(None)

    def _reset_ui(self) -> None:
        self._clear_layout()
        self.setWindowTitle(WINDOW_TITLE_SELECT_GAME)
        self._initialize_ui()

    def setup_ui(self) -> None:
        try:
            self._setup_title_bar()
            self._setup_content()
            self.main_layout.addWidget(self.interface_container)
        except Exception as e:
            ErrorHandler.handleError(f"Error setting up UI: {e}")

    def center_window(self) -> None:
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _setup_title_bar(self) -> None:
        title = WINDOW_TITLE_ENTRY if self.has_valid_selected_game else WINDOW_TITLE_SELECT_GAME
        self.setWindowTitle(title)
        title_bar = TitleBar(
            self,
            title=title,
            icon_path=APP_ICON_PATH,
            spacer_width=SPACER_WIDTH,
            show_max_button=SHOW_MAX_BUTTON,
            show_min_button=SHOW_MIN_BUTTON,
            show_close_button=SHOW_CLOSE_BUTTON,
            bar_height=BAR_HEIGHT
        )
        title_bar.create_title_bar()

    def _setup_content(self) -> None:
        self._init_table()
        self._init_spinner()
        self.interface_layout.addWidget(self.stacked_container)
        self.interface_layout.addWidget(self.button_manager.create_buttons())
        self.stacked_layout.setCurrentWidget(self.table)

    def _init_table(self) -> None:
        self.stacked_container = QWidget(self, styleSheet="background-color: rgba(0, 0, 0, 0.0);", sizePolicy=QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.stacked_layout = QStackedLayout(self.stacked_container)
        self.table = TableWidget(self)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(2)
        self.table.setWordWrap(False)
        self.table.setIconSize(QSize(32, 32))
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Name", "Path"])
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setStyleSheet("QHeaderView::section { font-weight: Bold; }") #color: #FFFFFF;
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().hide()
        #self.table.setShowGrid(False)
        #self.table.setMouseTracking(False)
        
        # UIComponents\CustomQfluentwidgets\table_view.py
        self.table.itemDelegate().setSelectedRowColor(color=None, alpha=22)
        self.table.itemDelegate().setHoverRowColor(color=None, alpha=4)    
        self.table.itemDelegate().setAlternateRowColor(color=None, alpha=2)
        self.table.itemDelegate().setPressedRowColor(color=None, alpha=8)
        self.table.itemDelegate().setPriorityOrder(["pressed", "selected", "hover", "alternate"])
        self.table.itemDelegate().setShowIndicator(False)
        self.table.itemDelegate().setRowBorderRadius(0)

        self.table.itemDoubleClicked.connect(lambda _: self.button_manager.select_game())
        self.stacked_layout.addWidget(self.table)
        self._populate_table()

    def _init_spinner(self) -> None:
        self.stacked_layout.addWidget(self.spinner_container)

    def _populate_table(self, is_rescan: bool = False) -> None:
        """Populate the table with available games from the registry."""
        games = self.game_manager.getGamesFromRegistry(emit_status=self._update_status, is_rescan=is_rescan)
        self.table.setRowCount(len(games))
        model = QFileSystemModel()
        model.setRootPath("")
        for row, (exe_name, exe_path) in enumerate(games.items()):
            folder_name = os.path.basename(os.path.dirname(exe_path))
            folder_path = os.path.dirname(exe_path)
            name_item = QTableWidgetItem(folder_name)
            name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            name_item.setIcon(model.fileIcon(model.index(exe_path)))
            path_item = QTableWidgetItem(folder_path)
            path_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            path_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, path_item)

    def _show_spinner(self) -> None:
        self.stacked_layout.setCurrentWidget(self.spinner_container)

    def _show_table(self) -> None:
        self.stacked_layout.setCurrentWidget(self.table)

class ButtonManager:
    def __init__(self, window: "SelectGameWindow"):
        self.window = window
        self.buttons = {}
        self.thread = None

    def create_buttons(self) -> QWidget:
        self._init_buttons()
        self._setup_layout()
        self.button_container = QWidget(self.window, objectName="ButtonContainer", fixedHeight=45)
        self.button_container.setLayout(self.button_layout)
        return self.button_container

    def _init_buttons(self) -> None:
        self.buttons["select"] = QPushButton("Select")
        self.buttons["select"].setFixedSize(80, 30)
        self.buttons["select"].clicked.connect(self.select_game)
        apply_tooltip(self.buttons["select"], "select_button")

        self.buttons["rescan"] = QPushButton("Rescan")
        self.buttons["rescan"].setFixedSize(80, 30)
        self.buttons["rescan"].clicked.connect(self.rescan_games)
        apply_tooltip(self.buttons["rescan"], "rescan_button")

        self.buttons["game_not_found"] = QLabel("Game Not Found?", self.window, styleSheet="color: rgba(255, 255, 255, 0.7); font-size: 12px; background-color: transparent;", cursor=Qt.PointingHandCursor)
        self.buttons["game_not_found"].setStyleSheet("QLabel:hover { color: white; }")
        apply_tooltip(self.buttons["game_not_found"], "game_not_found")

    def _setup_layout(self) -> None:
        self.button_layout = QHBoxLayout()
        self.button_layout.setContentsMargins(10, 0, 10, 0)
        self.button_layout.setSpacing(5)
        self.button_layout.addWidget(self.buttons["game_not_found"], alignment=Qt.AlignLeft)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.buttons["rescan"])
        self.button_layout.addWidget(self.buttons["select"])

    def select_game(self) -> None:
        """Initiate game selection and processing."""
        row = self.window.table.currentRow()
        if row >= 0:
            path = self.window.table.item(row, 1).text()
            self.window._show_spinner()
            for btn in self.buttons.values():
                btn.hide()
            self.thread = GameProcessingThread(path, self.window.config_manager, self.window.game_manager)
            self.thread.status_update.connect(self.window._update_status)
            self.thread.finished.connect(self._on_finished)
            self.thread.error.connect(self._on_error)
            self.thread.start()

    @Slot(dict)
    def _on_finished(self, content: dict) -> None:
        if not content:
            ErrorHandler.handleError("Failed to load game content. Please try again.")
            self.window.has_valid_selected_game = False
            self.window.config_manager.resetSelectedGame()
            self.window._show_table()
            self.window._update_status("")
            for btn in self.buttons.values():
                btn.show()
            return
        from Main import MainWindow
        self.window.main_window = MainWindow(self.window.config_manager, self.window.game_manager, content)
        self.window.main_window.show()
        self.window.close()

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        ErrorHandler.handleError(msg)
        self.window.has_valid_selected_game = False
        self.window.config_manager.resetSelectedGame()
        self.window._show_table()
        self.window._update_status("")
        for btn in self.buttons.values():
            btn.show()

    def rescan_games(self) -> None:
        self.window._show_spinner()
        self._do_rescan()

    def _do_rescan(self) -> None:
        try:
            self.window._populate_table(is_rescan=True)
            QTimer.singleShot(100, self._finalize_rescan)
        except Exception as e:
            ErrorHandler.handleError(f"Error during rescan: {e}")
            self._finalize_rescan()

    def _finalize_rescan(self) -> None:
        self.window._show_table()

def main(): 
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(APP_ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = SelectGameWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()