import sys
import os
from typing import Optional, Dict, List

from PySide6.QtCore import Qt, QSize, QUrl, QThread, Signal, QObject
from PySide6.QtGui import QIcon, QDesktopServices
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QWidget, QHBoxLayout, QFrame, 
                               QHeaderView, QPushButton, QFileIconProvider, QTableWidgetItem, 
                               QAbstractItemView, QLabel, QStackedLayout, QSizePolicy)

from qfluentwidgets import (TableWidget, setTheme, Theme, setThemeColor, BodyLabel, FluentIcon, InfoBar, InfoBarPosition)

from UIComponents.Personalization import BaseWindow
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.Tooltips import apply_tooltip
from UIComponents.Spinner import LoadingSpinner
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.ErrorHandler import ErrorHandler

TITLE = "FET TU Changelog Folders Renamer"
WINDOW_SIZE = (720, 480)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/ic_fluent_rename_24_filled.png"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"

class DataFetchWorker(QObject):
    finished = Signal(object)

    def __init__(self, game_manager: GameManager, config_manager: ConfigManager):
        super().__init__()
        self.game_manager = game_manager
        self.config_manager = config_manager

    def run(self):
        try:
            result = self.game_manager.getFETChangeFolders(self.config_manager)
            self.finished.emit(result)
        except Exception as e:
            ErrorHandler.handleError(f"Error fetching FET folder data: {e}")
            self.finished.emit(None)

class FETTUChangelogFoldersRenamer(BaseWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_manager = GameManager()
        self.config_manager = ConfigManager()
        self.folders_to_rename = []
        self.data_path = None
        
        self.loading_spinner = None
        self.loading_label = None
        self.thread = None
        self.worker = None

        self._initialize_window()

    def _initialize_window(self):
        self.setWindowTitle(TITLE)
        self.resize(*WINDOW_SIZE)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(50, 30, 50, 30)
        self.main_layout.setSpacing(0)
        try:
            self._setup_ui()
            self.show_loading()
            self._start_data_fetch()
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
            spacer_width=75,
            show_max_button=True,
            show_min_button=True,
            show_close_button=True,
            bar_height=32
        )
        title_bar.create_title_bar()

    def _setup_main_container(self):
        self.main_container = QWidget(self, styleSheet="background-color: transparent;")
        self.main_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_container_layout = QVBoxLayout(self.main_container)
        self.main_container_layout.setContentsMargins(0, 0, 0, 0)
        self.main_container_layout.setSpacing(0)
        self.main_layout.addWidget(self.main_container)

        self.stacked_container = QWidget(self.main_container, styleSheet="background-color: rgba(0, 0, 0, 0.0);", sizePolicy=QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.stacked_layout = QStackedLayout(self.stacked_container)
        self.main_container_layout.addWidget(self.stacked_container)

        self.table = TableWidget(self)
        self._configure_table()
        self.stacked_layout.addWidget(self.table)

        self.placeholder_label = QLabel(self, styleSheet="font-size: 14px; color: white; background-color: transparent;")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setWordWrap(True)
        self.stacked_layout.addWidget(self.placeholder_label)

        self.spinner_container = QWidget(self, styleSheet="background-color: transparent;")
        spinner_layout = QVBoxLayout(self.spinner_container)
        spinner_layout.setAlignment(Qt.AlignCenter)
        spinner_layout.setContentsMargins(0, 0, 0, 0)
        self.loading_spinner = LoadingSpinner(self)
        self.loading_spinner.setStyleSheet("background-color: transparent;")
        self.loading_label = QLabel("", self, styleSheet="font-size: 16px; color: white; background-color: transparent;", alignment=Qt.AlignCenter)
        spinner_layout.addWidget(self.loading_spinner, alignment=Qt.AlignCenter)
        spinner_layout.addWidget(self.loading_label, alignment=Qt.AlignCenter)
        self.stacked_layout.addWidget(self.spinner_container)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(SEPARATOR_STYLE)

        button_bar = self._create_button_bar()

        self.main_layout.addWidget(separator)
        self.main_layout.addWidget(button_bar)

    def _configure_table(self):
        self.table.setBorderVisible(False)
        self.table.setBorderRadius(0)
        self.table.setWordWrap(False)
        self.table.setIconSize(QSize(32, 32))
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setStyleSheet("QHeaderView::section { font-weight: Bold; }")
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        
        self.table.itemDelegate().setSelectedRowColor(color=None, alpha=0)
        self.table.itemDelegate().setHoverRowColor(color=None, alpha=0)    
        self.table.itemDelegate().setAlternateRowColor(color=None, alpha=2)
        self.table.itemDelegate().setPressedRowColor(color=None, alpha=0)
        self.table.itemDelegate().setPriorityOrder(["alternate", "selected", "pressed", "hover"])
        self.table.itemDelegate().setShowIndicator(False)
        self.table.itemDelegate().setRowBorderRadius(0)

    def _create_button_bar(self):
        bottom_widget = QWidget(fixedHeight=48)
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(15, 0, 15, 0)
        
        self.open_folder_button = QPushButton()
        self.open_folder_button.setIcon(FluentIcon.FOLDER.icon())
        self.open_folder_button.clicked.connect(self._open_folder)
        apply_tooltip(self.open_folder_button, "open_fet_data_folder_tooltip")

        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(FluentIcon.SYNC.icon())
        self.refresh_button.setIconSize(QSize(14, 14))
        self.refresh_button.clicked.connect(self._start_data_fetch)
        apply_tooltip(self.refresh_button, "refresh_folder_list_tooltip")
        
        self.status_label = BodyLabel("")
        
        self.rename_all_button = QPushButton("Rename All")
        self.rename_all_button.setEnabled(False)
        self.rename_all_button.clicked.connect(self._execute_rename_all)

        bottom_layout.addWidget(self.open_folder_button)
        bottom_layout.addWidget(self.refresh_button)
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.rename_all_button)
        return bottom_widget

    def show_loading(self):
        self.stacked_layout.setCurrentWidget(self.spinner_container)
        self.loading_label.setText("Loading...")

    def hide_loading(self):
        self.stacked_layout.setCurrentWidget(self.table)

    def show_placeholder(self, text):
        self.placeholder_label.setText(text)
        self.stacked_layout.setCurrentWidget(self.placeholder_label)

    def _start_data_fetch(self):
        self._cleanup_thread()
        self.show_loading()
        self.thread = QThread()
        self.worker = DataFetchWorker(self.game_manager, self.config_manager)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_data_fetched)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()

    def _on_data_fetched(self, result: Optional[Dict]):
        self.hide_loading()
        self.table.setRowCount(0)
        self.folders_to_rename.clear()
        
        self.data_path = result.get("path") if result else None
        
        provider = QFileIconProvider()
        folder_pixmap = provider.icon(QFileIconProvider.IconType.Folder).pixmap(QSize(16, 16), QIcon.Mode.Normal, QIcon.State.Off)
        static_folder_icon = QIcon(folder_pixmap)
        
        has_folders = result and result.get("folders")
        if not has_folders:
            relative_path = "Unknown"
            if self.data_path:
                parent_dir = os.path.basename(os.path.dirname(self.data_path))
                current_dir = os.path.basename(self.data_path)
                relative_path = os.path.join(parent_dir, current_dir)
            
            self.show_placeholder(f"No folders can be renamed in:\n{relative_path}")
            self.status_label.setText("")
            self.rename_all_button.setEnabled(False)
            self.open_folder_button.setEnabled(self.data_path is not None and os.path.exists(self.data_path))
            return
            
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Original Name (Patch ID)", "New Name (TU Version)"])
        header = self.table.horizontalHeader()
        for i in range(header.count()):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
            self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)

        self.table.setRowCount(len(result["folders"]))

        for row, folder_info in enumerate(result["folders"]):
            original_item = QTableWidgetItem(folder_info["original_name"])
            original_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            original_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            original_item.setIcon(static_folder_icon)
            original_item.setData(Qt.ItemDataRole.UserRole, folder_info)
            
            new_item = QTableWidgetItem(folder_info["new_name"])
            new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            new_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            
            self.table.setItem(row, 0, original_item)
            self.table.setItem(row, 1, new_item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        self.folders_to_rename = result["folders"]
        self.status_label.setText("")
        self.rename_all_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)

    def _execute_rename_all(self):
        if not self.folders_to_rename:
            return
        rename_ops = [self.table.item(i, 0).data(Qt.ItemDataRole.UserRole) for i in range(self.table.rowCount())]
        self._rename_folders(rename_ops)

    def _rename_folders(self, rename_ops: List[Dict]):
        if not rename_ops:
            return
            
        success_count = 0
        failed_ops = []
        rows_to_remove = []
        
        for idx, op in enumerate(rename_ops):
            try:
                original_path = op["original_path"]
                original_name = op["original_name"]
                new_name = op["new_name"]
                dir_path = os.path.dirname(original_path)
                new_path = os.path.join(dir_path, new_name)
                
                if not os.path.exists(original_path):
                    failed_ops.append(f"'{original_name}' was not found.")
                elif os.path.exists(new_path):
                    failed_ops.append(f"Could not rename '{original_name}' because '{new_name}' already exists.")
                    rows_to_remove.append(idx)
                else:
                    os.rename(original_path, new_path)
                    success_count += 1
                    rows_to_remove.append(idx)
            except Exception as e:
                ErrorHandler.handleError(f"Failed to rename '{op.get('original_name', 'Unknown')}': {e}")
                failed_ops.append(f"An unexpected error occurred with '{op.get('original_name', 'Unknown')}'.")
        
        for row in sorted(rows_to_remove, reverse=True):
            self.table.removeRow(row)
        
        total_count = len(rename_ops)
        if success_count > 0:
            InfoBar.success(
                title="Success",
                content=f"{success_count} of {total_count} folder(s) were successfully renamed.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

        if failed_ops:
            error_details = "\n".join(failed_ops)
            InfoBar.error(
                title="Rename Failed",
                content=f"{len(failed_ops)} folder(s) could not be renamed.\nDetails: {error_details}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=6000,
                parent=self
            )

        if self.table.rowCount() == 0:
            relative_path = "Unknown"
            if self.data_path:
                parent_dir = os.path.basename(os.path.dirname(self.data_path))
                current_dir = os.path.basename(self.data_path)
                relative_path = os.path.join(parent_dir, current_dir)
            self.show_placeholder(f"No folders can be renamed in:\n{relative_path}")
            self.status_label.setText("")
            self.rename_all_button.setEnabled(False)
            self.open_folder_button.setEnabled(self.data_path is not None and os.path.exists(self.data_path))

    def _open_folder(self):
        if self.data_path and os.path.exists(self.data_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.data_path))
        else:
            InfoBar.warning(
                title="Path Not Found",
                content="The target folder path could not be found or has not been determined yet.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
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
    
    icon = QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else QIcon()
    app.setWindowIcon(icon)
    
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = FETTUChangelogFoldersRenamer()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()