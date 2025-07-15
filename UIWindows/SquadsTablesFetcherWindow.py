import os
import sys
import time
from typing import List, Optional
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy, QPushButton,
    QTableWidgetItem, QLabel, QCompleter, QFileDialog, QHeaderView
)
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtCore import Qt, QUrl, QThread, Signal, QObject, QRunnable, QThreadPool, QEventLoop
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qframelesswindow import AcrylicWindow
from qfluentwidgets import (
    Theme, setTheme, setThemeColor, TableWidget, CheckBox, SearchLineEdit,
    FluentIcon, InfoBar, InfoBarPosition
)

from UIComponents.Personalization import AcrylicEffect
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.Spinner import LoadingSpinner
from UIWindows.SquadsTableSettingsWindow import TableSettingsWindow, TableSettings

from Core.Logger import logger
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.ErrorHandler import ErrorHandler

# Constants
TITLE = "Squads Tables Fetcher"
SIZE = (720, 480)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/FRICON.png"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = True
SHOW_MIN_BUTTON = True
SHOW_CLOSE_BUTTON = True

class NetworkConfig:
    RETRY_WAIT = 2
    TIMEOUT = 7000

class SquadsTablesFetcherWindow(AcrylicWindow):
    def __init__(self, index_url: Optional[str] = None, update_name: Optional[str] = None,
                 released_date: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.index_url = index_url
        self.update_name = update_name
        self.released_date = released_date
        self.game_manager = GameManager()
        self.config_manager = ConfigManager()
        self.button_manager = ButtonManager(self)
        self.tables_data: List[dict] = []
        self.checkbox_states: List[bool] = []
        self.table: Optional[TableWidget] = None
        self.fetching_label: Optional[QLabel] = None
        self.tables_label: Optional[QLabel] = None
        self.loading_spinner: Optional[LoadingSpinner] = None
        self.main_container: Optional[QWidget] = None
        self.checkbox_widgets: List[QWidget] = []
        self.search_line_edit: Optional[SearchLineEdit] = None
        self.completer: Optional[QCompleter] = None
        self.index_thread: Optional[QThread] = None
        self.index_worker: Optional[IndexFetchWorker] = None
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(12)
        self.active_fetch_workers = 0
        self.current_table = ""
        self.is_fetching_canceled = False
        self.start_time = None
        self.current_save_path = None
        self.db_fetched = False
        self.is_exact_search = False
        self._initialize_window()

    def _initialize_window(self):
        title = self._get_window_title()
        self.setWindowTitle(title)
        self.resize(*SIZE)
        AcrylicEffect(self)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(50, 30, 50, 30)
        self.main_layout.setSpacing(0)
        try:
            self._setup_ui()
            if self.index_url:
                self.show_loading(is_index=True)
                self.start_fetching_data()
        except Exception as e:
            self._on_error(f"Failed to initialize window: {str(e)}")

    def _get_window_title(self) -> str:
        if self.update_name and self.released_date:
            return f"{TITLE}: {self.update_name} ({self.released_date})"
        return TITLE

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    @staticmethod
    def center_child_window(parent_window, child_window):
        parent_geom = parent_window.frameGeometry()
        child_geom = child_window.frameGeometry()
        x = parent_geom.x() + (parent_geom.width() - child_geom.width()) // 2
        y = parent_geom.y() + (parent_geom.height() - child_geom.height()) // 2
        child_window.move(x, y)

    def _setup_ui(self):
        self._setup_title_bar()
        self._setup_search_bar()
        self._setup_main_container()
        self._setup_buttons()

    def _setup_title_bar(self):
        title_bar = TitleBar(
            window=self,
            title=self._get_window_title(),
            icon_path=ICON_PATH,
            spacer_width=SPACER_WIDTH,
            show_max_button=SHOW_MAX_BUTTON,
            show_min_button=SHOW_MIN_BUTTON,
            show_close_button=SHOW_CLOSE_BUTTON,
            bar_height=BAR_HEIGHT
        )
        title_bar.create_title_bar()

    def _setup_search_bar(self):
        self.search_line_edit = SearchLineEdit(self)
        self.search_line_edit.setPlaceholderText("Filter tables...")
        self.search_line_edit.setClearButtonEnabled(True)
        self.search_line_edit.textChanged.connect(self.filter_tables)
        self.search_line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.main_layout.addWidget(self.search_line_edit)

    def _setup_main_container(self):
        self.main_container = QWidget(self, styleSheet="background-color: transparent;")
        self.main_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_container_layout = QVBoxLayout(self.main_container)
        self.main_container_layout.setContentsMargins(0, 0, 0, 0)
        self.main_container_layout.setSpacing(0)
        self.main_layout.addWidget(self.main_container)

    def _setup_buttons(self):
        separator = QWidget(self, styleSheet="background-color: rgba(255, 255, 255, 0.1);")
        separator.setFixedHeight(1)
        self.main_layout.addWidget(separator)
        self.main_layout.addWidget(self.button_manager.create_buttons())

    def show_loading(self, is_index: bool = False):
        self.main_container_layout.setAlignment(Qt.AlignCenter)
        if self.table:
            self.table.hide()
        self._clear_loading_widgets()
        self.loading_spinner = LoadingSpinner(self)
        self.fetching_label = QLabel("Loading..." if is_index else "Fetching...", styleSheet="font-size: 16px; color: white;")
        self.tables_label = QLabel("", styleSheet=f"font-size: 14px; color: {THEME_COLOR};")
        for widget in [self.loading_spinner, self.fetching_label, self.tables_label]:
            self.main_container_layout.addWidget(widget, alignment=Qt.AlignCenter)

    def _clear_loading_widgets(self):
        for widget in [self.fetching_label, self.tables_label, self.loading_spinner]:
            if widget:
                widget.hide()
                widget.deleteLater()
        self.fetching_label = self.tables_label = self.loading_spinner = None

    def update_table_name(self, table_name: str):
        self.current_table = table_name
        if self.tables_label:
            self.tables_label.setText(table_name)
            self.tables_label.update()

    def hide_loading(self):
        self._clear_loading_widgets()
        if self.table:
            self.table.show()

    def _setup_tables(self):
        self.hide_loading()
        self.checkbox_widgets = []
        self.main_container_layout.setAlignment(Qt.AlignTop)
        self.table = TableWidget()
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(0)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(False)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Select", self.game_manager.getTableNameKey(),
            self.game_manager.getTableWrittenRecordsKey(),
            self.game_manager.getTableTotalRecordsKey(),
            self.game_manager.getTableSaveGroupsKey()
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionMode(TableWidget.SingleSelection)
        self.table.setEditTriggers(TableWidget.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setStyleSheet("QHeaderView::section { font-weight: Bold; }") #color: #FFFFFF;

        for i in range(self.table.columnCount()):
            self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(45)
        self.table.cellClicked.connect(self.on_cell_clicked)

        # UIComponents\CustomQfluentwidgets\table_view.py
        self.table.itemDelegate().setSelectedRowColor(color=None, alpha=0)
        self.table.itemDelegate().setHoverRowColor(color=None, alpha=0)    
        self.table.itemDelegate().setAlternateRowColor(color=None, alpha=2)
        self.table.itemDelegate().setPressedRowColor(color=None, alpha=0)
        self.table.itemDelegate().setPriorityOrder(["alternate", "selected", "pressed", "hover"])
        self.table.itemDelegate().setShowIndicator(False)

        self.main_container_layout.addWidget(self.table)


    def on_cell_clicked(self, row: int, column: int):
        checkbox_widget = self.table.cellWidget(row, 0)
        if checkbox_widget:
            checkbox = checkbox_widget.layout().itemAt(0).widget()
            new_state = not checkbox.isChecked()
            checkbox.setChecked(new_state)
            self.checkbox_states[row] = new_state
            self.button_manager.update_select_all_state()
            
    def start_fetching_data(self):
        self.index_thread = QThread()
        self.index_worker = IndexFetchWorker(self.index_url, self.game_manager, self.update_name)
        self.index_worker.moveToThread(self.index_thread)
        self.index_thread.started.connect(self.index_worker.run)
        self.index_worker.finished.connect(self.on_data_fetched)
        self.index_worker.error.connect(self._on_error)
        self.index_thread.finished.connect(self.index_thread.deleteLater)
        self.index_thread.start()

    def on_data_fetched(self, tables_data: List[dict]):
        if tables_data is None or not isinstance(tables_data, list):
            self._on_error("No tables data received from Index.json")
            return
        self.tables_data = tables_data
        self.checkbox_states = [self.config_manager.getConfigKeySelectAllTables()] * len(tables_data)
        self._setup_tables()
        self.table.setRowCount(len(tables_data))
        table_names = []
        for row, table in enumerate(tables_data):
            self._setup_table_row(row, table)
            table_name = table.get(self.game_manager.getTableNameKey(), "")
            table_names.append(table_name)
        self.table.resizeColumnsToContents()
        self._setup_completer(table_names)
        self.button_manager.select_all_checkbox.setEnabled(True)
        self.button_manager.exact_search_checkbox.setEnabled(True)
        self.button_manager.select_all_checkbox.stateChanged.connect(self.button_manager.toggle_select_all)
        self.button_manager.update_select_all_state(all(self.checkbox_states))
        self._cleanup_index_worker()
        self.hide_loading()

    def _setup_table_row(self, row: int, table: dict):
        checkbox = CheckBox()
        checkbox.setStyleSheet("margin-left: 10px; background-color: transparent;")
        checkbox.setChecked(self.checkbox_states[row])
        checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_state_changed(r, state))
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, 0, checkbox_widget)
        self.checkbox_widgets.append(checkbox_widget)
        table_name = table.get(self.game_manager.getTableNameKey(), "")
        if not table_name:
            logger.warning(f"No table name found for row {row}: {table}")
        self.table.setItem(row, 1, QTableWidgetItem(table_name))
        for col, key in enumerate([
            self.game_manager.getTableWrittenRecordsKey(),
            self.game_manager.getTableTotalRecordsKey(),
            self.game_manager.getTableSaveGroupsKey()
        ], 2):
            item = QTableWidgetItem(str(table.get(key, "")))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, col, item)

    def _setup_completer(self, table_names: List[str]):
        valid_names = [name for name in table_names if name]
        self.completer = QCompleter(valid_names, self.search_line_edit)
        self.completer.setCaseSensitivity(Qt.CaseSensitive if self.is_exact_search else Qt.CaseInsensitive)
        self.completer.setMaxVisibleItems(10)
        self.search_line_edit.setCompleter(self.completer)

    def toggle_exact_search(self, checked: bool):
        self.is_exact_search = checked
        if self.completer:
            self.completer.setCaseSensitivity(Qt.CaseSensitive if self.is_exact_search else Qt.CaseInsensitive)
            self.filter_tables(self.search_line_edit.text())

    def filter_tables(self, text: str):
        if not self.table:
            return
        text = text.lower()  
        for row in range(self.table.rowCount()):
            table_name = self.table.item(row, 1).text().lower() 
            self.table.setRowHidden(row, text not in table_name if not self.is_exact_search else text != table_name)

    def on_checkbox_state_changed(self, row: int, state: int):
        self.checkbox_states[row] = state == Qt.CheckState.Checked.value
        self.button_manager.update_select_all_state()

    def get_selected_tables(self) -> List[str]:
        if not self.table:
            return []
        selected = [
            self.table.item(row, 1).text()
            for row in range(self.table.rowCount())
            if self.checkbox_states[row] and not self.table.isRowHidden(row)
        ]
        valid_tables = [name for name in selected if name]
        if len(valid_tables) < len(selected):
            logger.warning(f"Excluded {len(selected) - len(valid_tables)} tables with empty names")
        return valid_tables

    def get_squad_folder_name(self) -> str:
        return f"{self.update_name.replace(' ', '_')}_Tables" if self.update_name else "Tables"

    def fetch_tables(self, selected_tables: List[str]):
        save_path = self._get_save_path()
        if not save_path:
            return
        logger.info(f"Start fetching {len(selected_tables)} tables to {save_path}")
        self.start_time = time.time()
        self.button_manager.disable_buttons()
        self.show_loading()
        self.active_fetch_workers = len(selected_tables)
        self.current_table = ""
        self.is_fetching_canceled = False
        self.fetched_tables = []
        self.db_fetched = False
        format = self.config_manager.getConfigKeyTableFormat()
        for table_name in selected_tables:
            if self.is_fetching_canceled:
                break
            worker = TableFetchWorker(
                self.index_url, table_name, save_path, format,
                self.game_manager, self.config_manager, self.tables_data, self.update_name
            )
            worker.signals.started.connect(self.update_table_name)
            worker.signals.finished.connect(self.on_table_fetched)
            worker.signals.error.connect(self._on_error)
            self.thread_pool.start(worker)
        if self.config_manager.getConfigKeyFetchSquadsDB() and self.game_manager.getDbName(self.index_url):
            db_filename = f"{self.update_name.replace(' ', '_')}{self.game_manager.getDbExtension()}" if self.update_name else f"Database{self.game_manager.getDbExtension()}"
            db_worker = TableFetchWorker(
                self.index_url, db_filename, save_path, None,
                self.game_manager, self.config_manager, self.tables_data, self.update_name
            )
            db_worker.signals.started.connect(lambda: self.update_table_name(db_filename))
            db_worker.signals.finished.connect(self.on_table_fetched)
            db_worker.signals.error.connect(self._on_error)
            self.thread_pool.start(db_worker)
            self.active_fetch_workers += 1

    def _get_save_path(self) -> Optional[str]:
        save_path = self.config_manager.getConfigKeyTableSavePath()
        if not save_path or not os.path.isdir(save_path):
            self.current_save_path = None
            self.db_fetched = False
            save_path = QFileDialog.getExistingDirectory(
                self, "Choose Folder to Save Tables", os.path.expanduser("~/Desktop")
            )
            if not save_path:
                return None
            self.current_save_path = save_path
        else:
            self.current_save_path = save_path
        return self.current_save_path

    def on_table_fetched(self, table_name: str):
        if self.is_fetching_canceled:
            return
        db_filename = f"{self.update_name.replace(' ', '_')}{self.game_manager.getDbExtension()}" if self.update_name else f"Database{self.game_manager.getDbExtension()}"
        if table_name == db_filename:
            self.db_fetched = True
        else:
            self.fetched_tables.append(table_name)
        self.active_fetch_workers -= 1
        logger.debug(f"Table fetched: {table_name}, remaining workers: {self.active_fetch_workers}")
        if self.active_fetch_workers <= 0:
            self._show_success_message()
            self.hide_loading()
            self.button_manager.enable_buttons()

    def _show_success_message(self):
        table_count = len(self.fetched_tables)
        save_path = self.current_save_path or ""
        save_path = os.path.abspath(save_path)
        if self.config_manager.getConfigKeySaveTablesInFolderUsingSquadFileName():
            save_path = os.path.join(save_path, self.get_squad_folder_name())
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        elapsed_time_str = f"{elapsed_time:.2f} seconds" if elapsed_time < 60 else f"{elapsed_time / 60:.2f} minutes"
        message = f"{table_count} {'Table' if table_count == 1 else 'Tables'}"
        if self.db_fetched:
            db_name = f"{self.update_name.replace(' ', '_')}{self.game_manager.getDbExtension()}" if self.update_name else f"Database{self.game_manager.getDbExtension()}"
            message += f" and {db_name}" if table_count > 0 else db_name
        message += f" fetched successfully in {elapsed_time_str} and saved to {save_path}"
        InfoBar.success(
            title="Success",
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2200,
            parent=self
        )
        logger.info(f"{message}")

    def toggle_select_all(self, checked: bool):
        if not self.table:
            return
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.checkbox_states[row] = checked
                checkbox_widget = self.table.cellWidget(row, 0)
                if checkbox_widget:
                    checkbox = checkbox_widget.layout().itemAt(0).widget()
                    checkbox.blockSignals(True)
                    checkbox.setChecked(checked)
                    checkbox.blockSignals(False)
        self.button_manager.update_select_all_state(checked)
        self.config_manager.setConfigKeySelectAllTables(checked)

    def _on_error(self, error_msg: str):
        if self.is_fetching_canceled:
            return
        self.is_fetching_canceled = True
        self.thread_pool.clear()
        self._cleanup_index_worker()
        ErrorHandler.handleError(error_msg)
        self.hide_loading()
        self.button_manager.enable_buttons()
        self.close()

    def _cleanup_index_worker(self):
        if self.index_worker:
            self.index_worker.cancel()
            if self.index_thread and self.index_thread.isRunning():
                self.index_thread.quit()
                self.index_thread.wait()
            self.index_worker.deleteLater()
            self.index_worker = None
            self.index_thread = None
            
    def closeEvent(self, event):
            self._cleanup_index_worker() 
            if self.thread_pool:
                self.thread_pool.clear()
                self.thread_pool.waitForDone()  # Wait for all workers to finish
            super().closeEvent(event)

class ButtonManager:
    def __init__(self, window: SquadsTablesFetcherWindow):
        self.window = window
        self.button_container: Optional[QWidget] = None
        self.buttons: dict = {}
        self.select_all_checkbox: Optional[CheckBox] = None

    def create_buttons(self) -> QWidget:
        self._init_buttons()
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.buttons["cancel"])
        button_layout.addStretch()
        button_layout.addWidget(self.exact_search_checkbox)
        button_layout.addWidget(self.select_all_checkbox)
        fetch_layout = QHBoxLayout()
        fetch_layout.setSpacing(0)
        fetch_layout.addWidget(self.buttons["fetch"])
        fetch_layout.addWidget(self.buttons["settings"])
        button_layout.addLayout(fetch_layout)
        self.button_container = QWidget(self.window)
        self.button_container.setLayout(button_layout)
        return self.button_container

    def _init_buttons(self):
        self.buttons = {
            "cancel": QPushButton("Cancel"),
            "fetch": QPushButton("Fetch Tables"),
            "settings": QPushButton()
        }
        self.buttons["cancel"].clicked.connect(self.cancel)
        self.buttons["fetch"].clicked.connect(self.fetch)
        self.buttons["fetch"].setStyleSheet("border-top-right-radius: 0px; border-bottom-right-radius: 0px;")
        self.buttons["fetch"].setFixedWidth(120)
        self.buttons["settings"].clicked.connect(self.open_table_settings)
        self.buttons["settings"].setIcon(FluentIcon.SETTING.icon(Theme.DARK))
        self.buttons["settings"].setStyleSheet(
            "QPushButton { border-top-left-radius: 0px; border-bottom-left-radius: 0px; "
            "border-left: 1px solid rgba(255, 255, 255, 0.1); }"
        )
        self.buttons["settings"].setFixedSize(28, 28)
        self.select_all_checkbox = CheckBox("Select All")
        self.select_all_checkbox.setChecked(self.window.config_manager.getConfigKeySelectAllTables())
        self.select_all_checkbox.setStyleSheet("margin-left: 5px; background-color: transparent;")
        self.select_all_checkbox.setEnabled(False)
        self.exact_search_checkbox = CheckBox("Exact Search")
        self.exact_search_checkbox.setStyleSheet("margin-left: 5px; background-color: transparent;")
        self.exact_search_checkbox.setEnabled(False)
        self.exact_search_checkbox.stateChanged.connect(self.on_exact_search_toggled)

    def on_exact_search_toggled(self, state: int):
        checked = state == Qt.CheckState.Checked.value
        self.window.toggle_exact_search(checked)

    def cancel(self):
        self.window._cleanup_index_worker()
        self.window.thread_pool.clear()
        self.window.close()

    def fetch(self):
        selected_tables = self.window.get_selected_tables()
        fetch_db = self.window.config_manager.getConfigKeyFetchSquadsDB() and self.window.game_manager.getDbName(self.window.index_url)
        if not selected_tables and not fetch_db:
            ErrorHandler.handleError("No valid tables selected and database fetch is not enabled")
            self.window.close()
            return
        self.window.fetch_tables(selected_tables)

    def open_table_settings(self):
        try:
            settings_window = TableSettingsWindow()
            SquadsTablesFetcherWindow.center_child_window(self.window, settings_window)
            settings_window.show()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to open settings window: {str(e)}")

    def toggle_select_all(self, state: int):
        checked = state == Qt.CheckState.Checked.value
        self.window.toggle_select_all(checked)

    def update_select_all_state(self, checked: Optional[bool] = None):
        if checked is None:
            checked = all(self.window.checkbox_states)
        self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setChecked(checked)
        self.select_all_checkbox.blockSignals(False)

    def disable_buttons(self):
        for btn in self.buttons.values():
            btn.setEnabled(False)
        self.select_all_checkbox.setEnabled(False)
        self.exact_search_checkbox.setEnabled(False)

    def enable_buttons(self):
        for btn in self.buttons.values():
            btn.setEnabled(True)
        self.select_all_checkbox.setEnabled(True)
        self.exact_search_checkbox.setEnabled(True)

class NetworkWorker:
    def __init__(self):
        self.network_manager: Optional[QNetworkAccessManager] = None
        self.current_reply: Optional[QNetworkReply] = None

    def _initialize_network_manager(self):
        self.network_manager = QNetworkAccessManager()

    def _cleanup_network(self):
        if self.current_reply:
            self.current_reply.abort()
            self.current_reply.deleteLater()
            self.current_reply = None
        if self.network_manager:
            self.network_manager.deleteLater()
            self.network_manager = None

    def fetch_data(self, url: str, max_retries: int) -> bytes:
        self._initialize_network_manager()
        for attempt in range(max_retries):
            try:
                request = QNetworkRequest(QUrl(url))
                request.setTransferTimeout(NetworkConfig.TIMEOUT)
                self.current_reply = self.network_manager.get(request)
                loop = QEventLoop()
                self.current_reply.finished.connect(loop.quit)
                loop.exec()
                if self.current_reply.error() == QNetworkReply.NoError:
                    data = self.current_reply.readAll().data()
                    self.current_reply.deleteLater()
                    self.current_reply = None
                    return data
                error_msg = self.current_reply.errorString()
                ErrorHandler.handleError(f"Error fetching data on attempt {attempt + 1}: {error_msg}")
                self.current_reply.deleteLater()
                self.current_reply = None
                if attempt < max_retries - 1:
                    time.sleep(NetworkConfig.RETRY_WAIT)
                else:
                    raise Exception(f"Failed to fetch data after {max_retries} attempts: {error_msg}")
            except Exception as e:
                ErrorHandler.handleError(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(NetworkConfig.RETRY_WAIT)
                else:
                    raise
        return b""

class IndexFetchWorker(QObject, NetworkWorker):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, index_url: str, game_manager: GameManager, update_name: Optional[str] = None):
        super().__init__()
        self.index_url = index_url
        self.game_manager = game_manager
        self.update_name = update_name or "Unknown Squad"

    def run(self):
        try:
            tables_data = self.game_manager.getTablesData(self.index_url)
            if tables_data is None or not tables_data:
                error_msg = "No tables data found in Index.json"
                self.error.emit(error_msg)
                return
            logger.info(f"Index.json for {self.update_name} fetched successfully and found {len(tables_data)} tables in it")
            self.finished.emit(tables_data)
        except Exception as e:
            error_msg = f"Failed to fetch Index.json from {self.index_url}: {str(e)}"
            self.error.emit(error_msg)
        finally:
            self._cleanup_network()

    def cancel(self):
        self._cleanup_network()

class TableFetchWorker(QRunnable, NetworkWorker):
    class Signals(QObject):
        started = Signal(str)
        finished = Signal(str)
        error = Signal(str)

    def __init__(self, index_url: str, table_name: str, save_path: str, format: str,
                 game_manager: GameManager, config_manager: ConfigManager, tables_data: List[dict],
                 update_name: Optional[str] = None):
        super().__init__()
        self.signals = self.Signals()
        self.index_url = index_url
        self.table_name = table_name
        self.save_path = save_path
        self.format = format
        self.game_manager = game_manager
        self.config_manager = config_manager
        self.tables_data = tables_data
        self.update_name = update_name
        self.is_canceled = False

    def run(self):
        if self.is_canceled or not self.table_name:
            error_msg = f"Skipping fetch for empty {'database file' if self.format is None else 'table'} name: {self.table_name}"
            ErrorHandler.handleError(error_msg)
            self.signals.error.emit(error_msg)
            return
        format_config = {
            self.game_manager.getTableExtension(): (self.game_manager.getTableExtension(), lambda c, p: c.to_csv(p)),
            ".json": (".json", lambda c, p: c.to_json(p)),
            ".txt (UTF-8 BOM)": (".txt", lambda c, p: c.to_utf8bom_txt(p)),
            ".txt (UTF-16 LE)": (".txt", lambda c, p: c.to_utf16le_txt(p))
        }
        try:
            if self.format is None:
                file_path = os.path.normpath(os.path.join(self.save_path, self.table_name))
            else:
                ext, save_method = format_config.get(
                    self.format, (self.game_manager.getTableExtension(), lambda c, p: c.to_csv(p))
                )
                if self.format not in format_config:
                    logger.warning(f"Invalid format '{self.format}' selected, falling back to {self.game_manager.getTableExtension()}")
                folder_path = self.save_path
                if self.config_manager.getConfigKeySaveTablesInFolderUsingSquadFileName():
                    folder_path = os.path.join(self.save_path, f"{self.update_name.replace(' ', '_')}_Tables" if self.update_name else "Tables")
                file_path = os.path.normpath(os.path.join(folder_path, f"{self.table_name}{ext}"))
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            table_url = (
                self.game_manager.getDbPathKey(self.index_url, self.config_manager)
                if self.format is None
                else self.game_manager.getTableUrl(self.index_url, self.table_name, self.config_manager)
            )
            if not table_url:
                raise Exception(f"Failed to get URL for {'database file' if self.format is None else 'table'}: {self.table_name}")
            self.signals.started.emit(self.table_name)
            if self.is_canceled:
                return
            data = self.fetch_data(table_url, self.game_manager.MAX_RETRIES)
            if self.is_canceled:
                logger.info(f"Fetch canceled after data retrieval for {'database file' if self.format is None else 'table'}: {self.table_name}")
                return
            if self.format is None:
                with open(file_path, "wb") as f:
                    f.write(data)
            else:
                table_info = next(
                    (t for t in self.tables_data if t.get(self.game_manager.getTableNameKey()) == self.table_name),
                    None
                )
                converter = TableSettings(data, self.table_name, self.config_manager, table_info, self.index_url)
                save_method(converter, file_path)
            if self.is_canceled:
                logger.info(f"Fetch canceled after saving for {'database file' if self.format is None else 'table'}: {self.table_name}")
                return
            self.signals.finished.emit(self.table_name)
        except PermissionError as e:
            error_msg = f"Permission denied when saving {'database file' if self.format is None else 'table'} {self.table_name} to {file_path}: {str(e)}"
            ErrorHandler.handleError(error_msg)
            self.signals.error.emit(error_msg)
        except Exception as e:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except PermissionError:
                    logger.warning(f"Could not delete file {file_path} due to permission error")
            error_msg = f"Failed to download {'database file' if self.format is None else 'table'} {self.table_name}: {str(e)}"
            ErrorHandler.handleError(error_msg)
            self.signals.error.emit(error_msg)
        finally:
            self._cleanup_network()

    def cancel(self):
        self.is_canceled = True
        self._cleanup_network()

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = SquadsTablesFetcherWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()