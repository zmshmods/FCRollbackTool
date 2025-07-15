import sys
from typing import Optional, Dict
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QWidget, QTableWidgetItem, QSizePolicy, QHeaderView, QLabel
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QThread, Signal, QObject
from qfluentwidgets import TableWidget, Theme, setTheme, setThemeColor
from qframelesswindow import AcrylicWindow

from UIComponents.Personalization import AcrylicEffect
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.Spinner import LoadingSpinner

from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.ErrorHandler import ErrorHandler

TITLE = "Live Editor Compatibility Info"
SIZE = (720, 480)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/ic_fluent_comp_24_filled.png"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = True
SHOW_MIN_BUTTON = True
SHOW_CLOSE_BUTTON = True

class DataFetchWorker(QObject):
    finished = Signal(dict)

    def __init__(self, game_manager: GameManager, config_manager: ConfigManager):
        super().__init__()
        self.game_manager = game_manager
        self.config_manager = config_manager

    def run(self):
        try:
            data = self.game_manager.fetchLiveEditorVersionsData(self.config_manager)
            if not data:
                ErrorHandler.handleError("Failed to fetch version.json data")
                return
            self.finished.emit({
                "data": data,
                "game_ver": self.game_manager.getGameSemVer(self.config_manager),
                "le_ver": self.game_manager.getLiveEditorVersion(self.config_manager)
            })
        except Exception as e:
            ErrorHandler.handleError(f"Error fetching data: {e}")

class LiveEditorCompatibilityInfo(AcrylicWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_manager = GameManager()
        self.config_manager = ConfigManager()
        self.table: Optional[TableWidget] = None
        self.table_status: Optional[TableWidget] = None
        self.loading_spinner: Optional[LoadingSpinner] = None
        self.main_container: Optional[QWidget] = None
        self.thread: Optional[QThread] = None
        self.worker: Optional[DataFetchWorker] = None
        self._initialize_window()

    def _initialize_window(self):
        self.setWindowTitle(TITLE)
        self.resize(*SIZE)
        AcrylicEffect(self)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(50, 30, 50, 30)
        self.main_layout.setSpacing(0)
        try:
            self._setup_ui()
            self.show_loading()
            self._start_fetching_data()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to initialize window: {e}")
            self._cleanup_thread()
            self.close()

    def _setup_ui(self):
        self._setup_title_bar()
        self._setup_main_container()

    def _setup_title_bar(self):
        title_bar = TitleBar(
            window=self,
            title=TITLE,
            icon_path=ICON_PATH,
            spacer_width=SPACER_WIDTH,
            show_max_button=SHOW_MAX_BUTTON,
            show_min_button=SHOW_MIN_BUTTON,
            show_close_button=SHOW_CLOSE_BUTTON,
            bar_height=BAR_HEIGHT
        )
        title_bar.create_title_bar()

    def _setup_main_container(self):
        self.main_container = QWidget(self, styleSheet="background-color: transparent;")
        self.main_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_container_layout = QVBoxLayout(self.main_container)
        self.main_container_layout.setContentsMargins(0, 0, 0, 0)
        self.main_container_layout.setSpacing(0)
        self.main_layout.addWidget(self.main_container)

    def show_loading(self):
        self.main_container_layout.setAlignment(Qt.AlignCenter)
        if self.table: self.table.hide()
        if self.table_status: self.table_status.hide()
        self.loading_spinner = LoadingSpinner(self)
        self.fetching_label = QLabel("Loading...", self)
        self.fetching_label.setStyleSheet("font-size: 16px; color: white;")
        
        self.main_container_layout.addWidget(self.loading_spinner, alignment=Qt.AlignCenter)
        self.main_container_layout.addWidget(self.fetching_label, alignment=Qt.AlignCenter)

    def hide_loading(self):
        if self.loading_spinner:
            self.loading_spinner.hide()
            self.loading_spinner.deleteLater()
            self.loading_spinner = None
        if self.fetching_label:
            self.fetching_label.hide()
            self.fetching_label.deleteLater()
            self.fetching_label = None
        if self.table:
            self.table.show()
        if self.table_status:
            self.table_status.show()

    def _setup_tables(self):
        self.table = TableWidget()
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(0)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(False)
        self.table.itemDelegate().setShowIndicator(False)
        self.table.verticalHeader().setDefaultSectionSize(45)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["SemVer", "Title Update", "Live Editor Version"])
        header = self.table.horizontalHeader()
        header.setStyleSheet("QHeaderView::section { font-weight: Bold; }")
        header.setMinimumSectionSize(120)
        self.table.setSelectionMode(TableWidget.NoSelection)
        self.table.setEditTriggers(TableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        for i in range(3):
            self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.verticalHeader().hide()
        self.table.itemDelegate().setSelectedRowColor(color=None, alpha=0)
        self.table.itemDelegate().setHoverRowColor(color=None, alpha=0)
        self.table.itemDelegate().setAlternateRowColor(color=None, alpha=2)
        self.table.itemDelegate().setPressedRowColor(color=None, alpha=0)
        self.table.itemDelegate().setPriorityOrder(["alternate", "selected", "pressed", "hover"])
        self.main_container_layout.addWidget(self.table)

        self.table_status = TableWidget()
        self.table_status.setBorderVisible(True)
        self.table_status.setBorderRadius(0)
        self.table_status.setWordWrap(False)
        self.table_status.setSortingEnabled(False)
        self.table_status.itemDelegate().setShowIndicator(False)
        self.table_status.setColumnCount(3)
        self.table_status.setRowCount(1)
        self.table_status.setHorizontalHeaderLabels(["Your Game TU", "Your LE Version", "is Compatible?"])
        header = self.table_status.horizontalHeader()
        header.setStyleSheet("QHeaderView::section { font-weight: bold; color: #FFF; }")
        header.setMinimumSectionSize(120)
        self.table_status.setSelectionMode(TableWidget.NoSelection)
        self.table_status.setEditTriggers(TableWidget.NoEditTriggers)
        self.table_status.horizontalHeader().setStretchLastSection(True)
        for i in range(3):
            self.table_status.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)
        self.table_status.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table_status.verticalHeader().hide()
        self.table_status.setFixedHeight(75)
        self.table_status.itemDelegate().setSelectedRowColor(color=None, alpha=0)
        self.table_status.itemDelegate().setHoverRowColor(color=None, alpha=0)
        self.table_status.itemDelegate().setAlternateRowColor(color=None, alpha=0)
        self.table_status.itemDelegate().setPressedRowColor(color=None, alpha=0)
        self.table_status.itemDelegate().setPriorityOrder(["alternate", "selected", "pressed", "hover"])
        self.main_container_layout.addWidget(self.table_status)

    def _start_fetching_data(self):
        self.thread = QThread()
        self.worker = DataFetchWorker(self.game_manager, self.config_manager)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_data_fetched)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()

    def _on_data_fetched(self, result: Dict):
        self.hide_loading()
        self._setup_tables()
        game_ver_data = result["data"].get("game_ver", {})
        compat = result["data"].get("compatibility", {})
        self.table.setRowCount(len(game_ver_data))
        sorted_versions = sorted(game_ver_data.items(), key=lambda x: x[0], reverse=True)
        for row_idx, (sem_ver, tu) in enumerate(sorted_versions):
            item = QTableWidgetItem(sem_ver)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, item)
            item = QTableWidgetItem(tu if tu else sem_ver)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, item)
            le_range = compat.get(sem_ver, [])
            le_text = f"{le_range[0]} to {le_range[1]}" if len(le_range) == 2 else ""
            item = QTableWidgetItem(le_text)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, item)
        self.table.resizeColumnsToContents()

        game_sem_ver = result["game_ver"]
        le_ver = result["le_ver"] or "Unknown"
        game_tu = game_ver_data.get(game_sem_ver, game_sem_ver if game_sem_ver else "Unknown")
        item = QTableWidgetItem(game_tu)
        item.setTextAlignment(Qt.AlignCenter)
        self.table_status.setItem(0, 0, item)
        item = QTableWidgetItem(le_ver)
        item.setTextAlignment(Qt.AlignCenter)
        self.table_status.setItem(0, 1, item)
        is_compat = self._check_compatibility(game_sem_ver, le_ver, compat)
        compat_item = QTableWidgetItem("Yes" if is_compat == True else "No" if is_compat == False else "Unknown")
        compat_item.setForeground(Qt.green if is_compat == True else Qt.red if is_compat == False else Qt.yellow)
        compat_item.setTextAlignment(Qt.AlignCenter)
        self.table_status.setItem(0, 2, compat_item)
        self.table_status.resizeColumnsToContents()

    def _check_compatibility(self, sem_ver: Optional[str], le_ver: Optional[str], compat: Dict) -> Optional[bool]:
        if not sem_ver or not le_ver or le_ver == "Unknown" or not compat or sem_ver not in compat or len(compat[sem_ver]) != 2:
            return None

        try:
            # split versions into parts
            le_ver_parts = [int(x) for x in le_ver.replace("v", "").strip().split(".")]
            min_ver_parts = [int(x) for x in compat[sem_ver][0].replace("v", "").strip().split(".")]
            max_ver_parts = [int(x) for x in compat[sem_ver][1].replace("v", "").strip().split(".")]

            # find length
            max_length = max(len(le_ver_parts), len(min_ver_parts), len(max_ver_parts))

            # pad with zeros for consistent comparison
            le_ver_parts += [0] * (max_length - len(le_ver_parts))
            min_ver_parts += [0] * (max_length - len(min_ver_parts))
            max_ver_parts += [0] * (max_length - len(max_ver_parts))

            # range check
            if le_ver_parts[0] != min_ver_parts[0] or le_ver_parts[0] != max_ver_parts[0]:
                return False
            if le_ver_parts[1] < min_ver_parts[1] or le_ver_parts[1] > max_ver_parts[1]:
                return False
            if le_ver_parts[1] == min_ver_parts[1] and le_ver_parts[2] < min_ver_parts[2]:
                return False
            if le_ver_parts[1] == max_ver_parts[1] and le_ver_parts[2] > max_ver_parts[2]:
                return False

            return True

        except ValueError:
            return None
        
    def closeEvent(self, event):
        self._cleanup_thread()
        super().closeEvent(event)

    def _cleanup_thread(self):
        if self.thread:
            if self.thread.isRunning():
                self.thread.quit()
                self.thread.wait()
            self.thread.deleteLater()
            self.thread = None
        self.worker = None

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = LiveEditorCompatibilityInfo()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()