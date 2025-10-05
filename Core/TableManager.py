import os
import subprocess
from typing import List
from PySide6.QtWidgets import (QVBoxLayout, QHeaderView, QFrame, QTableWidgetItem, 
                               QAbstractItemView, QApplication)
from PySide6.QtCore import Qt, QFileSystemWatcher, Signal, QDateTime, QPoint, QUrl
from PySide6.QtGui import QColor, QAction, QDesktopServices
from qfluentwidgets import TableWidget, FluentIcon, RoundMenu

from Core.Logger import logger
from Core.MainDataManager import MainDataManager
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.ErrorHandler import ErrorHandler

class BaseTable(QFrame):
    table_updated_signal = Signal()
    HEADER_HEIGHT = 32
    NAME_COLUMN_WIDTH = 220

    def __init__(self, parent=None, game_content=None, config_manager=None, game_manager=None, profile_type=None, tab_key=None):
        super().__init__(parent)
        self.game_content = game_content or {}
        self.config_manager = config_manager or ConfigManager()
        self.game_manager = game_manager or GameManager()
        self.main_data_manager = MainDataManager()
        self.profile_type = profile_type
        self.tab_key = tab_key
        self.profile_directories = {}
        self.specific_monitor_dir = None
        self.table = None
        self.watcher = None
        self.game_settings_folder_watcher = None
        self.visible_headers = None
        self.ALL_TABLE_HEADERS = None
        self.content_key = None
        self.uses_sha1 = False
        self.sha1_key = None
        self.STATUS_MAPPING = {}
        self.STATUS_PRIORITY = []
        self.ordered_headers = None

        if not self.profile_type:
            raise ValueError(f"Profile type must be set in {self.__class__.__name__}")
        if not self.tab_key:
            raise ValueError(f"Tab key must be set in {self.__class__.__name__}")

        self._initialize_components()

    def _initialize_components(self):
        self._initialize_profile_directories()
        self._setup_ui()
        self._configure_table()
        self._setup_file_watcher()
        try:
            self.config_manager.register_config_updated_callback(self._on_config_updated)
            logger.debug(f"Registered config updated callback for {self.tab_key}")
        except AttributeError as e:
            ErrorHandler.handleError(f"Failed to register config updated callback: {e}")

    def _on_config_updated(self, tab_key: str):
        if tab_key == self.tab_key or tab_key == "Visual_TableColumns":
            self.visible_headers = self.config_manager.getConfigKeyTableColumns(self.tab_key)
            self.update_table()

    def update_table(self, path=None):
        try:
            if not self.game_content:
                logger.debug(f"No game content for {self.tab_key}")
                return
            self.populate_table()
            logger.debug(f"{self.tab_key} Table updated")
            self.table_updated_signal.emit()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update {self.tab_key} table: {str(e)}")
            raise

    def populate_table(self):
        self.config_manager.loadConfig()
        updates = self.game_content.get(self.content_key, [])
        if not updates:
            self.table.setRowCount(0)
            logger.debug(f"No updates found for {self.tab_key}")
            return

        self.visible_headers = self.config_manager.getConfigKeyTableColumns(self.tab_key)
        self.ordered_headers = self._order_headers()
        self.table.setColumnCount(len(self.ordered_headers))
        self.table.setHorizontalHeaderLabels(self.ordered_headers)
        self.table.setRowCount(len(updates))

        profile_files = self._get_profile_directories()
        current_sha_config = self.config_manager.getConfigKeySHA1() if self.uses_sha1 else ""

        for row, update in enumerate(updates):
            update_sha = update.get(self.sha1_key, "")
            if self.uses_sha1 and current_sha_config and update_sha == current_sha_config:
                name_key = self._get_name_key()
                logger.debug(f"Found installed update: {update.get(name_key, 'Unknown')} with SHA1 {update_sha}")
            self._fill_table_row(row, update, current_sha_config, profile_files)

        for col_idx, header in enumerate(self.ordered_headers):
            name_key = self._get_name_key()
            if header == name_key:
                self.table.setColumnWidth(col_idx, self.NAME_COLUMN_WIDTH)
            else:
                self.table.resizeColumnToContents(col_idx)

        header = self.table.horizontalHeader()
        for col in range(len(self.ordered_headers)):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        header.setSectionResizeMode(len(self.ordered_headers) - 1, QHeaderView.Stretch)

        self.table.show()

    def update_visible_columns(self, columns: List[str]):
        name_key = self._get_name_key()
        mandatory_columns = [name_key, "Status"]
        valid_columns = [col for col in columns if col in self.ALL_TABLE_HEADERS and col not in mandatory_columns]
        self.visible_headers = mandatory_columns + valid_columns
        self.config_manager.setConfigKeyTableColumns(self.tab_key, self.visible_headers)
        self._setup_ui()
        self.populate_table()

    def _initialize_profile_directories(self):
        selected_game_config = self.config_manager.getConfigKeySelectedGame()
        if selected_game_config:
            game_id = self.game_manager.getSelectedGameId(selected_game_config)
            base_dir = self.game_manager.getProfileDirectory(game_id, self.profile_type)
            self.profile_directories[game_id] = base_dir
            
            if self.tab_key == self.game_manager.getTabKeyTitleUpdates():
                self.specific_monitor_dir = base_dir
            elif self.tab_key == self.game_manager.getTabKeySquadsUpdates():
                self.specific_monitor_dir = os.path.join(base_dir, self.game_manager.getContentKeySquad())
            elif self.tab_key == self.game_manager.getTabKeyFutSquadsUpdates():
                self.specific_monitor_dir = os.path.join(base_dir, self.game_manager.getContentKeyFutSquad())

            if self.specific_monitor_dir:
                os.makedirs(self.specific_monitor_dir, exist_ok=True)
                
        else:
            logger.warning(f"No selected game found during initialization for {self.tab_key}")
            self._initialize_default_profiles()

    def _initialize_default_profiles(self):
        for profile in self.game_manager.profile_manager.get_all_profiles():
            game_id = profile.id
            try:
                base_dir = self.game_manager.getProfileDirectory(game_id, self.profile_type)
                self.profile_directories[game_id] = base_dir
                if self.tab_key == self.game_manager.getTabKeyTitleUpdates():
                    self.specific_monitor_dir = base_dir
                elif self.tab_key == self.game_manager.getTabKeySquadsUpdates():
                    self.specific_monitor_dir = os.path.join(base_dir, self.game_manager.getContentKeySquad())
                elif self.tab_key == self.game_manager.getTabKeyFutSquadsUpdates():
                    self.specific_monitor_dir = os.path.join(base_dir, self.game_manager.getContentKeyFutSquad())
            except ValueError as e:
                ErrorHandler.handleError(f"Failed to initialize profile for {game_id}: {e}")

    def _get_profile_directories(self):
        if self.specific_monitor_dir and os.path.exists(self.specific_monitor_dir):
            selected_game = self.config_manager.getConfigKeySelectedGame()
            if not selected_game:
                logger.warning(f"No selected game found for {self.tab_key}, returning empty profile files")
                return {}
            short_name = self.game_manager.getSelectedGameId(selected_game) or ""
            files_and_dirs = set(os.listdir(self.specific_monitor_dir))
            logger.debug(f"Retrieved profile files for {short_name} in {self.specific_monitor_dir}")
            return {short_name: files_and_dirs}
        logger.debug(f"No specific monitor directory or directory does not exist: {self.specific_monitor_dir}")
        return {}

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setStyleSheet("background-color: transparent;")
        self.table = TableWidget(self)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(0)
        self.table.setWordWrap(False)
        layout.addWidget(self.table)

    def _configure_table(self):
        header = self.table.horizontalHeader()
        header.setStyleSheet("QHeaderView::section { font-weight: Bold; }")
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(100)
        header.setFixedHeight(self.HEADER_HEIGHT)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(45)

        self.table.itemDelegate().setSelectedRowColor(color=None, alpha=22)
        self.table.itemDelegate().setHoverRowColor(color=None, alpha=10)
        self.table.itemDelegate().setAlternateRowColor(color=None, alpha=2)
        self.table.itemDelegate().setPressedRowColor(color=None, alpha=15)
        self.table.itemDelegate().setPriorityOrder(["pressed", "selected", "hover", "alternate"])
        self.table.itemDelegate().setShowIndicator(True)
        self.table.itemDelegate().setRowBorderRadius(0)
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    def _setup_file_watcher(self):
        self.watcher = QFileSystemWatcher(self)
        if self.specific_monitor_dir and os.path.exists(self.specific_monitor_dir):
            self.watcher.addPath(self.specific_monitor_dir)
            logger.debug(f"File watcher set up for profile directory: {self.specific_monitor_dir}")
        self.watcher.directoryChanged.connect(self.update_table)

        if self.tab_key in [self.game_manager.getTabKeySquadsUpdates(), self.game_manager.getTabKeyFutSquadsUpdates()]:
            self.game_settings_folder_watcher = QFileSystemWatcher(self)
            settings_path = self.game_manager.getGameSettingsFolderPath(self.config_manager.getConfigKeySelectedGame())
            if settings_path and os.path.exists(settings_path):
                self.game_settings_folder_watcher.addPath(settings_path)
                logger.debug(f"File watcher set up for game settings directory: {settings_path}")
            self.game_settings_folder_watcher.directoryChanged.connect(self.update_table)

    def _show_context_menu(self, pos: QPoint):
        item = self.table.itemAt(pos)
        if not item:
            return

        row = item.row()
        updates_list = self.game_content.get(self.content_key, [])
        if row >= len(updates_list):
            return
            
        update_data = updates_list[row]
        menu = RoundMenu(parent=self.table)

        def add_copy_action(key, display_name, icon=FluentIcon.COPY):
            value = update_data.get(key)
            if value:
                action = QAction(f"Copy {display_name}", menu)
                action.setIcon(icon.icon())
                action.triggered.connect(lambda checked=False, text=value: QApplication.clipboard().setText(str(text)))
                menu.addAction(action)

        if self.tab_key == self.game_manager.getTabKeyTitleUpdates():
            add_copy_action(self.game_manager.getTitleUpdateNameKey(), "Name")
            add_copy_action(self.game_manager.getTitleUpdateSemVerKey(), "Semantic Version")
            add_copy_action(self.game_manager.getTitleUpdatePatchIDKey(), "Patch ID")
            add_copy_action(self.game_manager.getTitleUpdateSHA1Key(), "SHA1", icon=FluentIcon.FINGERPRINT)
            add_copy_action(self.game_manager.getTitleUpdateReleasedDateKey(), "Release Date")
            add_copy_action(self.game_manager.getTitleUpdateRelativeDateKey(), "Relative Date")
            add_copy_action(self.game_manager.getTitleUpdateDownloadURLKey(), "Download URL")
            menu.addSeparator()
            add_copy_action(self.game_manager.getTitleUpdateMainManifestIDKey(), "Main Manifest ID")
            add_copy_action(self.game_manager.getTitleUpdateEngUsManifestIDKey(), "eng_us Manifest ID")

        elif self.tab_key in [self.game_manager.getTabKeySquadsUpdates(), self.game_manager.getTabKeyFutSquadsUpdates()]:
            add_copy_action(self._get_name_key(), "Name")
            add_copy_action(self._get_released_date_key(), "Release Date")
            add_copy_action(self._get_relative_date_key(), "Relative Date")
            add_copy_action(self.game_manager.getSquadsBuildDateKey(), "Build Date")
            add_copy_action(self.game_manager.getSquadsReleasedOnTUKey(), "Released On TU")
            add_copy_action(self.game_manager.getSquadsSizeKey(), "Size")
            add_copy_action(self.game_manager.getSquadsDbMajorKey(), "DB Major Version")

        update_name = update_data.get(self._get_name_key())
        if update_name and self.specific_monitor_dir:
            found_path = None
            for ext in self.main_data_manager.getCompressedFileExtensions() + [""]:
                potential_path = os.path.join(self.specific_monitor_dir, update_name + ext)
                if os.path.exists(potential_path):
                    found_path = potential_path
                    break
            
            if found_path:
                menu.addSeparator()
                locate_action = QAction("Locate in Profile Folder", menu)
                locate_action.setIcon(FluentIcon.FOLDER.icon())
                locate_action.triggered.connect(lambda: self._open_file_in_explorer(found_path))
                menu.addAction(locate_action)

        if menu.actions():
            menu.exec(self.table.mapToGlobal(pos))

    def _open_file_in_explorer(self, path: str):
        try:
            if os.name == 'nt':
                subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
        except Exception as e:
            ErrorHandler.handleError(f"Failed to open file in explorer: {e}")

    def _order_headers(self):
        if not self.visible_headers:
            name_key = self._get_name_key()
            self.visible_headers = [name_key, "Status"]
        default_order = self.game_manager.getColumnOrderForTable(self.tab_key)
        headers = self.visible_headers.copy()
        name_key = self._get_name_key()
        ordered_headers = sorted(
            [col for col in headers if col not in [name_key, "Status"]],
            key=lambda x: default_order.index(x) if x in default_order else len(default_order)
        )
        return [name_key] + ordered_headers + ["Status"]

    def _get_name_key(self) -> str:
        if self.tab_key == self.game_manager.getTabKeyTitleUpdates():
            return self.game_manager.getTitleUpdateNameKey()
        elif self.tab_key == self.game_manager.getTabKeySquadsUpdates():
            return self.game_manager.getSquadsNameKey()
        elif self.tab_key == self.game_manager.getTabKeyFutSquadsUpdates():
            return self.game_manager.getFutSquadsNameKey()
        raise ValueError(f"Invalid tab_key: {self.tab_key}")

    def _get_released_date_key(self) -> str:
        if self.tab_key == self.game_manager.getTabKeyTitleUpdates():
            return self.game_manager.getTitleUpdateReleasedDateKey()
        elif self.tab_key == self.game_manager.getTabKeySquadsUpdates():
            return self.game_manager.getSquadsReleasedDateKey()
        elif self.tab_key == self.game_manager.getTabKeyFutSquadsUpdates():
            return self.game_manager.getFutSquadsReleasedDateKey()
        raise ValueError(f"Invalid tab_key: {self.tab_key}")

    def _get_relative_date_key(self) -> str:
        if self.tab_key == self.game_manager.getTabKeyTitleUpdates():
            return self.game_manager.getTitleUpdateRelativeDateKey()
        elif self.tab_key == self.game_manager.getTabKeySquadsUpdates():
            return self.game_manager.getSquadsRelativeDateKey()
        elif self.tab_key == self.game_manager.getTabKeyFutSquadsUpdates():
            return self.game_manager.getFutSquadsRelativeDateKey()
        raise ValueError(f"Invalid tab_key: {self.tab_key}")

    def _fill_table_row(self, row, update, current_sha_config, profile_files):

        name_key = self._get_name_key()
        released_date_key = self._get_released_date_key()
        relative_date_key = self._get_relative_date_key()
        for col, header in enumerate(self.ordered_headers):
            if header == "Status":
                item = self._create_non_editable_item("", align_left=False)
                self._set_status_item(item, update, current_sha_config, profile_files)
                self.table.setItem(row, col, item)
            elif header == released_date_key:
                value = update.get(header, "N/A")
                display_value = value
                if value != "N/A":
                    # Check if date is ISO format and reformat it for display
                    if 'T' in value and value.endswith('Z'):
                        dt = QDateTime.fromString(value, Qt.ISODate)
                        if dt.isValid():
                            # Format to "Mon Day, Year"
                            display_value = dt.toString("MMM d, yyyy")

                item = self._create_non_editable_item(display_value, align_left=False)
                self.table.setItem(row, col, item)
            elif header == relative_date_key:
                value = update.get(released_date_key, "N/A")
                if value != "N/A":
                    is_title_update = self.tab_key == self.game_manager.getTabKeyTitleUpdates()
                    relative_date = self.game_manager.getRelativeDate(value, is_title_update)
                    display_value = relative_date
                else:
                    display_value = "Invalid Date"
                item = self._create_non_editable_item(display_value, align_left=False)
                self.table.setItem(row, col, item)
            else:
                value = update.get(header, "N/A")
                align_left = (header == name_key)
                item = self._create_non_editable_item(value, align_left=align_left)
                self.table.setItem(row, col, item)

    def _set_status_item(self, item, update, current_sha_config, profile_files):
        selected_game = self.config_manager.getConfigKeySelectedGame()
        if not selected_game:
            logger.warning(f"No selected game found for status update in {self.tab_key}")
            item.setText("No Game Selected")
            item.setForeground(Qt.red)
            return
        short_name = self.game_manager.getSelectedGameId(selected_game) or ""
        normalized_files = {file.strip().lower() for file in profile_files.get(short_name, set())}
        
        download_url_key = self.game_manager.getDownloadURLKeyForTab(self.tab_key)
        released_date_key = self._get_released_date_key()
        
        released_date = update.get(released_date_key, "N/A")
        relative_date = self.game_manager.getRelativeDate(released_date, self.tab_key == self.game_manager.getTabKeyTitleUpdates()) if released_date != "N/A" else ""
        download_url = update.get(download_url_key, "")

        for status_key in self.STATUS_PRIORITY:
            status = self.STATUS_MAPPING[status_key]
            condition = status["condition"]
            if status_key in ["ComingInConfirmed", "NotAddedToList"]:
                args = (self, update, current_sha_config, normalized_files, self.sha1_key, download_url, relative_date) if self.uses_sha1 else (self, update, normalized_files, download_url, relative_date)
            else:
                args = (self, update, current_sha_config, normalized_files, self.sha1_key) if self.uses_sha1 else (self, update, normalized_files)
            
            if condition(*args):
                if status_key == "ComingInConfirmed" and relative_date:
                    item.setText(f"Coming In {relative_date.replace('In ', '')}... (Confirmed)")
                else:
                    item.setText(status["text"])
                item.setForeground(status["color"])
                item.setData(Qt.UserRole, status_key)
                break

    def _is_update_available(self, update_name, normalized_files):
        if not update_name:
            return False
        update_name_lower = update_name.strip().lower()
        compressed_extensions = self.main_data_manager.getCompressedFileExtensions()
        for file_or_dir in normalized_files:
            if any(file_or_dir.endswith(ext) for ext in compressed_extensions):
                base_name = os.path.splitext(file_or_dir)[0].strip().lower()
                if base_name == update_name_lower:
                    return True
            else:
                if file_or_dir.strip().lower() == update_name_lower:
                    return True
        return False

    def _is_update_installed(self, update_name):
        settings_path = self.game_manager.getGameSettingsFolderPath(self.config_manager.getConfigKeySelectedGame())
        if not update_name or not settings_path or not os.path.exists(settings_path):
            return False
        update_name_lower = update_name.strip().lower()
        try:
            normalized_files = {file.strip().lower() for file in os.listdir(settings_path)}
            for file in normalized_files:
                if file == update_name_lower or os.path.splitext(file)[0].strip().lower() == update_name_lower:
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking installed squad in {settings_path}: {e}")
            return False

    def _create_non_editable_item(self, text, align_left=False):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter if align_left else Qt.AlignCenter | Qt.AlignVCenter)
        return item

class TitleUpdateTable(BaseTable):
    def __init__(self, parent=None, game_content=None, config_manager=None, game_manager=None, profile_type=None, tab_key=None):
        super().__init__(
            parent=parent,
            game_content=game_content,
            config_manager=config_manager,
            game_manager=game_manager,
            profile_type=profile_type or game_manager.getProfileTypeTitleUpdate(),
            tab_key=tab_key or game_manager.getTabKeyTitleUpdates()
        )
        self.ALL_TABLE_HEADERS = self.game_manager.getAvailableColumnsForTable(self.tab_key)
        self.visible_headers = self.config_manager.getConfigKeyTableColumns(self.tab_key)
        self.content_key = self.game_manager.getContentKeyTitleUpdate()
        self.uses_sha1 = True
        self.sha1_key = self.game_manager.getTitleUpdateSHA1Key()
        self.STATUS_MAPPING = {
            "Installed": {
                "text": "Installed (Current)",
                "color": Qt.green,
                "condition": lambda self, update, sha1, files, key: update.get(key) == sha1
            },
            "ReadyToInstall": {
                "text": "Ready To Install (Stored In Profile)",
                "color": Qt.yellow,
                "condition": lambda self, update, sha1, files, key: self._is_update_available(update.get(self.game_manager.getTitleUpdateNameKey(), "").strip().lower(), files)
            },
            "ComingInConfirmed": {
                "text": "Coming In ... (Confirmed)",
                "color": QColor(255, 165, 0),  # Orange
                "condition": lambda self, update, sha1, files, key, download_url, relative_date: not download_url and relative_date.startswith("In ")
            },
            "AvailableForDownload": {
                "text": "Available For Download",
                "color": Qt.lightGray,
                "condition": lambda self, update, sha1, files, key: bool(update.get(self.game_manager.getDownloadURLKeyForTab(self.tab_key), ""))
            },
            "NotAddedToList": {
                "text": "No Download URL added yet",
                "color": Qt.red,
                "condition": lambda self, update, sha1, files, key, download_url, relative_date: not download_url and relative_date.endswith(" ago")
            }
        }
        self.STATUS_PRIORITY = ["Installed", "ReadyToInstall", "ComingInConfirmed", "AvailableForDownload", "NotAddedToList"]

class SquadsUpdatesTable(BaseTable):
    def __init__(self, parent=None, game_content=None, config_manager=None, game_manager=None, profile_type=None, tab_key=None):
        super().__init__(
            parent=parent,
            game_content=game_content,
            config_manager=config_manager,
            game_manager=game_manager,
            profile_type=profile_type or game_manager.getProfileTypeSquad(),
            tab_key=tab_key or game_manager.getTabKeySquadsUpdates()
        )
        self.ALL_TABLE_HEADERS = self.game_manager.getAvailableColumnsForTable(self.tab_key)
        self.visible_headers = self.config_manager.getConfigKeyTableColumns(self.tab_key)
        self.content_key = self.game_manager.getContentKeySquad()
        self.uses_sha1 = False
        self.STATUS_MAPPING = {
            "Installed": {
                "text": "Installed",
                "color": Qt.green,
                "condition": lambda self, update, files: self._is_update_installed(update.get(self.game_manager.getSquadsNameKey(), "").strip().lower())
            },
            "ReadyToInstall": {
                "text": "Ready To Install (Stored In Profile)",
                "color": Qt.yellow,
                "condition": lambda self, update, files: self._is_update_available(update.get(self.game_manager.getSquadsNameKey(), "").strip().lower(), files)
            },
            "ComingInConfirmed": {
                "text": "Coming In ... (Confirmed)",
                "color": QColor(255, 165, 0),  # Orange
                "condition": lambda self, update, files, download_url, relative_date: not download_url and relative_date.startswith("In ")
            },
            "AvailableForDownload": {
                "text": "Available For Download",
                "color": Qt.lightGray,
                "condition": lambda self, update, files: bool(update.get(self.game_manager.getDownloadURLKeyForTab(self.tab_key), ""))
            },
            "NotAddedToList": {
                "text": "No Download URL added yet",
                "color": Qt.red,
                "condition": lambda self, update, files, download_url, relative_date: not download_url and relative_date.endswith(" ago")
            }
        }
        self.STATUS_PRIORITY = ["Installed", "ReadyToInstall", "ComingInConfirmed", "AvailableForDownload", "NotAddedToList"]

class FutSquadsUpdatesTable(BaseTable):
    def __init__(self, parent=None, game_content=None, config_manager=None, game_manager=None, profile_type=None, tab_key=None):
        super().__init__(
            parent=parent,
            game_content=game_content,
            config_manager=config_manager,
            game_manager=game_manager,
            profile_type=profile_type or game_manager.getProfileTypeSquad(),
            tab_key=tab_key or game_manager.getTabKeyFutSquadsUpdates()
        )
        self.ALL_TABLE_HEADERS = self.game_manager.getAvailableColumnsForTable(self.tab_key)
        self.visible_headers = self.config_manager.getConfigKeyTableColumns(self.tab_key)
        self.content_key = self.game_manager.getContentKeyFutSquad()
        self.uses_sha1 = False
        self.STATUS_MAPPING = {
            "Installed": {
                "text": "Installed",
                "color": Qt.green,
                "condition": lambda self, update, files: self._is_update_installed(update.get(self.game_manager.getFutSquadsNameKey(), "").strip().lower())
            },
            "ReadyToInstall": {
                "text": "Ready To Install (Stored In Profile)",
                "color": Qt.yellow,
                "condition": lambda self, update, files: self._is_update_available(update.get(self.game_manager.getFutSquadsNameKey(), "").strip().lower(), files)
            },
            "ComingInConfirmed": {
                "text": "Coming In ... (Confirmed)",
                "color": QColor(255, 165, 0),  # Orange
                "condition": lambda self, update, files, download_url, relative_date: not download_url and relative_date.startswith("In ")
            },
            "AvailableForDownload": {
                "text": "Available For Download",
                "color": Qt.lightGray,
                "condition": lambda self, update, files: bool(update.get(self.game_manager.getDownloadURLKeyForTab(self.tab_key), ""))
            },
            "NotAddedToList": {
                "text": "No Download URL added yet",
                "color": Qt.red,
                "condition": lambda self, update, files, download_url, relative_date: not download_url and relative_date.endswith(" ago")
            }
        }
        self.STATUS_PRIORITY = ["Installed", "ReadyToInstall", "ComingInConfirmed", "AvailableForDownload", "NotAddedToList"]