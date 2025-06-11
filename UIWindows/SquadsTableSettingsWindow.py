import sys
import json
import csv
import io
import os
from typing import List, Optional

from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QPushButton,
    QSpacerItem, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from qframelesswindow import AcrylicWindow
from qfluentwidgets import CheckBox, ComboBox, LineEdit, Theme, setTheme, setThemeColor, CaptionLabel, SimpleCardWidget, FluentIcon

from Core.Initializer import ConfigManager, ErrorHandler, GameManager
from Core.Logger import logger
from UIComponents.Tooltips import apply_tooltip
from UIComponents.Personalization import AcrylicEffect
from UIComponents.TitleBar import TitleBar
from UIComponents.MainStyles import MainStyles

# Constants
WINDOW_TITLE = "Table Settings"
WINDOW_SIZE = (520, 420)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/FRICON.png"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = False

# Unified styles
TITLE_STYLE = "font-weight: bold; color: white; font-size: 16px;"
DESC_STYLE = "color: rgba(255, 255, 255, 0.7); font-size: 12px;"
TEXT_STYLE = "background-color: transparent; color: white; font-size: 14px;"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"

# Settings options
COLUMN_ORDER_ITEMS = ["AsRead", "BitOffset", "DbMeta"]
RECORD_TYPE_ITEMS = ["Written Records Only", "Total Records"]
RECORD_TYPE_CONFIG = ["WrittenRecords", "TotalRecords"]
SAVE_TYPE_ITEMS = [".csv", ".json", ".txt (UTF-8 BOM)", ".txt (UTF-16 LE)"]
TABLE_NAME_KEYS = ["Name", "TableName", "table_name", "name"]
FORMAT_CONFIG = {
    ".csv": (".csv", lambda c, p: c.to_csv(p)),
    ".json": (".json", lambda c, p: c.to_json(p)),
    ".txt (UTF-8 BOM)": (".txt", lambda c, p: c.to_utf8bom_txt(p)),
    ".txt (UTF-16 LE)": (".txt", lambda c, p: c.to_utf16le_txt(p))
}

class TableSettings:
    """Handles table data processing and formatting based on user settings."""
    def __init__(self, csv_data: bytes, table_name: str, config_manager: ConfigManager,
                 table_info: dict = None, index_url: str = None):
        self.csv_data = csv_data
        self.table_name = table_name
        self.config_manager = config_manager
        self.table_info = table_info
        self.index_url = index_url
        self.game_manager = GameManager()

    def _apply_total_records(self, rows: List[List[str]], headers: List[str]) -> List[List[str]]:
        """Append default records to meet total records if configured."""
        if self.table_info and self.config_manager.getConfigKeyGetRecordsAs() == "TotalRecords":
            total_records = self.table_info.get("TotalRecords", 0)
            written_records = self.table_info.get("WrittenRecords", 0)
            default_record = self.table_info.get("DefaultRecord")
            records_to_add = total_records - written_records
            if records_to_add > 0 and default_record and default_record != "null":
                default_values = default_record.split(",")
                if len(default_values) == len(headers):
                    rows.extend([default_values] * records_to_add)
        return rows

    def _reorder_columns(self, rows: List[List[str]], headers: List[str]) -> tuple[List[List[str]], List[str]]:
        """Reorder columns based on the configured column order."""
        order_type = self.config_manager.getConfigKeyColumnOrder()
        squad_type = self.game_manager.getSquadTypeFromIndexUrl(self.index_url) if self.index_url else "Squads"

        if order_type == "BitOffset":
            return rows, headers
        elif order_type == "AsRead" and self.table_info:
            column_order = self.table_info.get("ColumnReadOrder", "").split(",")
            if len(column_order) != len(headers):
                return rows, headers
            new_headers = [
                self.game_manager.getColumnMetaName(self.table_name, short_name.strip(), self.config_manager, squad_type)
                for short_name in column_order
                if self.game_manager.getColumnMetaName(self.table_name, short_name.strip(), self.config_manager, squad_type) in headers
            ]
            if len(new_headers) != len(headers):
                return rows, headers
            header_indices = [headers.index(h) for h in new_headers]
            return [[row[i] for i in header_indices] for row in rows], new_headers
        elif order_type == "DbMeta":
            meta_order = self.game_manager.getTableMetaColumnOrder(self.table_name, self.config_manager, squad_type)
            if not meta_order or len(meta_order) != len(headers):
                return rows, headers
            header_indices = [headers.index(h) for h in meta_order if h in headers]
            if len(header_indices) != len(headers):
                return rows, headers
            return [[row[i] for i in header_indices] for row in rows], meta_order
        return rows, headers

    def to_csv(self, output_path: str) -> str:
        """Save table data as CSV."""
        rows = list(csv.reader(io.StringIO(self.csv_data.decode('utf-8-sig'))))
        if not rows:
            raise ValueError("No headers found in CSV data")
        headers = rows[0]
        rows = self._apply_total_records(rows, headers)
        rows, headers = self._reorder_columns(rows, headers)
        with open(output_path, "w", newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerows([headers] + rows[1:])
        return output_path

    def to_json(self, output_path: str) -> str:
        """Save table data as JSON."""
        rows = list(csv.reader(io.StringIO(self.csv_data.decode('utf-8-sig'))))
        if not rows:
            raise ValueError("No headers found in CSV data")
        headers = rows[0]
        rows = self._apply_total_records(rows, headers)
        rows, headers = self._reorder_columns(rows, headers)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([dict(zip(headers, row)) for row in rows[1:]], f, ensure_ascii=False, indent=4) # non-ASCII characters
        return output_path

    def to_utf8bom_txt(self, output_path: str) -> None:
        """Save table data as UTF-8 BOM text."""
        rows = list(csv.reader(io.StringIO(self.csv_data.decode('utf-8-sig'))))
        if not rows:
            raise ValueError("No headers found in CSV data")
        headers = rows[0]
        rows = self._apply_total_records(rows, headers)
        rows, headers = self._reorder_columns(rows, headers)
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            f.write('\t'.join(headers) + '\n')
            for row in rows[1:]:
                f.write('\t'.join(row) + '\n')

    def to_utf16le_txt(self, output_path: str) -> None:
        """Save table data as UTF-16 LE text."""
        rows = list(csv.reader(io.StringIO(self.csv_data.decode('utf-8-sig'))))
        if not rows:
            raise ValueError("No headers found in CSV data")
        headers = rows[0]
        rows = self._apply_total_records(rows, headers)
        rows, headers = self._reorder_columns(rows, headers)
        with open(output_path, "w", encoding="utf-16") as f:
            f.write('\t'.join(headers) + '\n')
            for row in rows[1:]:
                f.write('\t'.join(row) + '\n')

class TableSettingsWindow(AcrylicWindow):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.config_mgr = ConfigManager()
        self.button_manager = ButtonManager(self)
        self.save_type_combo = None
        self.column_order_combo = None
        self.get_records_combo = None
        self.save_path_edit = None
        self.squad_folder_cb = None
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*WINDOW_SIZE)
        AcrylicEffect(self)
        self.setWindowModality(Qt.ApplicationModal)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        try:
            self.setup_ui()
            self.button_manager._update_reset_button_state()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to setup UI: {str(e)}")

    def setup_ui(self) -> None:
        """Initialize the UI components."""
        self._setup_title_bar()
        self._setup_content_container()
        self._setup_buttons()

    def center_window(self) -> None:
        """Center the window on the screen."""
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _setup_title_bar(self) -> None:
        """Configure the title bar."""
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

    def _setup_content_container(self) -> None:
        """Setup the main content container with settings widgets."""
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(0)

        # desc = CaptionLabel("Configure Table Settings", self)
        # desc.setStyleSheet(DESC_STYLE)
        # self.content_layout.addWidget(desc)

        # self.content_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

        content_widget = self._create_table_settings_content()
        self.content_layout.addWidget(content_widget)

        self.content_layout.addStretch()
        self.main_layout.addWidget(self.content_container)

    def _setup_buttons(self) -> None:
        """Setup the buttons container."""
        separator = self._create_separator(height=1)
        self.main_layout.addWidget(separator)
        button_container = self.button_manager.create_buttons()
        self.main_layout.addWidget(button_container if button_container else QWidget())

    def _create_separator(self, width: Optional[int] = None, height: Optional[int] = None) -> QWidget:
        """Create a separator widget with specified dimensions."""
        separator = QWidget()
        separator.setStyleSheet(SEPARATOR_STYLE)
        if width is not None:
            separator.setFixedWidth(width)
        if height is not None:
            separator.setFixedHeight(height)
        return separator

    def _create_table_settings_content(self) -> QWidget:
        """Create the content for table settings."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = SimpleCardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        # Column Order By
        column_order_container = QWidget()
        column_order_layout = QHBoxLayout(column_order_container)
        column_order_layout.setContentsMargins(0, 0, 0, 0)
        column_order_layout.setSpacing(0)

        column_order_label = QLabel("Column Order By:")
        column_order_label.setStyleSheet(TEXT_STYLE)

        self.column_order_combo = ComboBox()  
        self.column_order_combo.addItems(COLUMN_ORDER_ITEMS)
        self.column_order_combo.setCurrentText(self.config_mgr.getConfigKeyColumnOrder())
        self.column_order_combo.setFixedSize(300, 28)
        apply_tooltip(self.column_order_combo, "columnOrderOptions")
        self.column_order_combo.activated.connect(lambda index: self.on_column_order_changed(self.column_order_combo.itemText(index)))

        column_order_layout.addWidget(column_order_label)
        column_order_layout.addStretch()
        column_order_layout.addWidget(self.column_order_combo)

        card_layout.addWidget(column_order_container)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Get Records As
        get_records_container = QWidget()
        get_records_layout = QHBoxLayout(get_records_container)
        get_records_layout.setContentsMargins(0, 0, 0, 0)
        get_records_layout.setSpacing(0)

        get_records_label = QLabel("Get Records As:")
        get_records_label.setStyleSheet(TEXT_STYLE)

        get_records_as = self.config_mgr.getConfigKeyGetRecordsAs() or RECORD_TYPE_CONFIG[0]
        try:
            get_records_as_index = RECORD_TYPE_CONFIG.index(get_records_as)
            get_records_as_default = RECORD_TYPE_ITEMS[get_records_as_index]
        except ValueError:
            get_records_as_default = RECORD_TYPE_ITEMS[0]

        self.get_records_combo = ComboBox()  
        self.get_records_combo.addItems(RECORD_TYPE_ITEMS)
        self.get_records_combo.setCurrentText(get_records_as_default)
        self.get_records_combo.setFixedSize(300, 28)
        apply_tooltip(self.get_records_combo, "getRecordsOptions")
        self.get_records_combo.activated.connect(lambda index: self.on_record_type_changed(self.get_records_combo.itemText(index)))

        get_records_layout.addWidget(get_records_label)
        get_records_layout.addStretch()
        get_records_layout.addWidget(self.get_records_combo)

        card_layout.addWidget(get_records_container)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Save As Type
        save_type_container = QWidget()
        save_type_layout = QHBoxLayout(save_type_container)
        save_type_layout.setContentsMargins(0, 0, 0, 0)
        save_type_layout.setSpacing(0)

        save_type_label = QLabel("Save As Type:")
        save_type_label.setStyleSheet(TEXT_STYLE)

        self.save_type_combo = ComboBox()  
        self.save_type_combo.addItems(SAVE_TYPE_ITEMS)
        self.save_type_combo.setCurrentText(self.config_mgr.getConfigKeyTableFormat())
        self.save_type_combo.setFixedSize(300, 28)
        apply_tooltip(self.save_type_combo, "saveTypeOptions")
        self.save_type_combo.activated.connect(lambda index: self.on_save_type_changed(self.save_type_combo.itemText(index)))

        save_type_layout.addWidget(save_type_label)
        save_type_layout.addStretch()
        save_type_layout.addWidget(self.save_type_combo)

        card_layout.addWidget(save_type_container)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Save Path
        save_path_container = QWidget()
        save_path_layout = QVBoxLayout(save_path_container)
        save_path_layout.setContentsMargins(0, 0, 0, 0)
        save_path_layout.setSpacing(10)

        # Horizontal row for label and button
        top_row = QWidget()
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(5)

        save_path_label = QLabel("Save Path:")
        save_path_label.setStyleSheet(TEXT_STYLE)

        self.browse_button = QPushButton("Browse")  
        # self.browse_button.setIcon(FluentIcon.FOLDER.icon())
        self.browse_button.setFixedSize(300, 28)
        apply_tooltip(self.browse_button, "browseButton")
        self.browse_button.clicked.connect(self.on_browse_save_path)

        top_layout.addWidget(save_path_label)
        top_layout.addStretch()
        top_layout.addWidget(self.browse_button)

        # Text field below
        self.save_path_edit = LineEdit()  
        self.save_path_edit.setMinimumHeight(28)
        self.save_path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.save_path_edit.setPlaceholderText("Set path or leave it empty to be asked each time")
        self.save_path_edit.setText(self.config_mgr.getConfigKeyTableSavePath() or "")
        self.save_path_edit.textChanged.connect(self.on_save_path_changed)

        # Add everything to the main vertical layout
        save_path_layout.addWidget(top_row)
        save_path_layout.addWidget(self.save_path_edit)

        card_layout.addWidget(save_path_container)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Fetch Squads DB Checkbox
        self.fetch_squads_db_cb = CheckBox("Fetch squads .db file")
        self.fetch_squads_db_cb.setStyleSheet(TEXT_STYLE)
        self.fetch_squads_db_cb.setChecked(self.config_mgr.getConfigKeyFetchSquadsDB())
        self.fetch_squads_db_cb.stateChanged.connect(self.on_fetch_squads_db_changed)
        card_layout.addWidget(self.fetch_squads_db_cb)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Squad Folder Checkbox
        self.squad_folder_cb = CheckBox("Save tables in a subfolder named using the squad file name")  
        self.squad_folder_cb.setStyleSheet(TEXT_STYLE)
        self.squad_folder_cb.setChecked(self.config_mgr.getConfigKeySaveTablesInFolderUsingSquadFileName())
        self.squad_folder_cb.stateChanged.connect(self.on_squad_folder_changed)

        card_layout.addWidget(self.squad_folder_cb)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def on_column_order_changed(self, order: str) -> None:
        """Handle column order selection changes."""
        try:
            self.config_mgr.setConfigKeyColumnOrder(order)
            #logger.debug(f"Column order updated to: {order}")
            self.button_manager._update_reset_button_state()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update column order: {str(e)}")

    def on_record_type_changed(self, record_type: str) -> None:
        """Handle record type selection changes."""
        try:
            config_value = RECORD_TYPE_CONFIG[RECORD_TYPE_ITEMS.index(record_type)]
            self.config_mgr.setConfigKeyGetRecordsAs(config_value)
            #logger.debug(f"Record type updated to: {config_value}")
            self.button_manager._update_reset_button_state()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update record type: {str(e)}")

    def on_save_type_changed(self, format_type: str) -> None:
        try:
            if format_type not in FORMAT_CONFIG:
                format_type = ".txt (UTF-8 BOM)"  # Default fallback
                logger.warning(f"Invalid save type '{format_type}', falling back to .txt (UTF-8 BOM)")
            self.config_mgr.setConfigKeyTableFormat(format_type)
            logger.debug(f"Table format updated to: {format_type}")
            self.button_manager._update_reset_button_state()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update table format: {str(e)}")

    def on_save_path_changed(self, save_path: str) -> None:
        """Handle save path changes."""
        try:
            self.config_mgr.setConfigKeyTableSavePath(save_path)
            #logger.debug(f"Save path updated to: {save_path}")
            self.button_manager._update_reset_button_state()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update save path: {str(e)}")

    def on_fetch_squads_db_changed(self, state: int) -> None:
        """Handle fetch squads database checkbox state changes."""
        try:
            checked = bool(state == Qt.CheckState.Checked.value)
            self.config_mgr.setConfigKeyFetchSquadsDB(checked)
            logger.debug(f"Fetch squads database setting updated to: {checked}")
            self.button_manager._update_reset_button_state()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update fetch squads database setting: {str(e)}")

    def on_squad_folder_changed(self, state: int) -> None:
        """Handle squad folder checkbox state changes."""
        try:
            checked = bool(state == Qt.CheckState.Checked.value)
            self.config_mgr.setConfigKeySaveTablesInFolderUsingSquadFileName(checked)
            #logger.debug(f"Squad folder setting updated to: {checked}")
            self.button_manager._update_reset_button_state()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update squad folder setting: {str(e)}")

    def on_browse_save_path(self) -> None:
        """Handle browse button click for save path."""
        try:
            folder_path = QFileDialog.getExistingDirectory(
                parent=self,
                caption="Select Save Path",
                dir=os.path.join(os.path.expanduser("~"), "Desktop")
            )
            if folder_path:
                self.config_mgr.setConfigKeyTableSavePath(folder_path)
                #logger.debug(f"Save path updated to: {folder_path}")
                self.save_path_edit.setText(folder_path)
                self.button_manager._update_reset_button_state()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to browse save path: {str(e)}")


    def close(self) -> None:
        """Close the window."""
        try:
            QApplication.processEvents()
            super().close()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to close window: {str(e)}")

class ButtonManager:
    """Manages button actions for TableSettingsWindow."""
    def __init__(self, window: "TableSettingsWindow"):
        self.window = window
        self.button_container = None
        self.buttons = {}
        self.button_layout = None

    def create_buttons(self) -> Optional[QWidget]:
        """Create and configure buttons."""
        try:
            self._init_buttons()
            self._setup_layout()
            self.button_container = QWidget(self.window)
            self.button_container.setLayout(self.button_layout)
            return self.button_container
        except Exception as e:
            ErrorHandler.handleError(f"Error creating buttons: {str(e)}")
            fallback_container = QWidget(self.window)
            fallback_layout = QHBoxLayout(fallback_container)
            fallback_layout.addStretch()
            logger.warning("Returning fallback button container due to error.")
            return fallback_container

    def _init_buttons(self) -> None:
        """Initialize buttons with consistent styling."""
        button_configs = {
            "reset": "Reset All",
            "done": "Done",
        }
        for name, text in button_configs.items():
            try:
                btn = QPushButton(text)
                if name == "reset":
                    apply_tooltip(btn, "resetAllTablesSettings")
                self.buttons[name] = btn
            except Exception as e:
                self.buttons[name] = QPushButton(f"{text} (Error)")

    def _setup_layout(self) -> None:
        """Setup the button layout."""
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        for name in ["reset", "done"]:
            if name in self.buttons:
                btn = self.buttons[name]
                if name == "reset":
                    btn.clicked.connect(self._reset_to_default)
                elif name == "done":
                    btn.clicked.connect(self.window.close)
                self.button_layout.addWidget(btn)

    def _reset_to_default(self) -> None:
        """Reset all settings to their default values."""
        try:
            # Reset settings in ConfigManager
            self.window.config_mgr.resetTableSettingsToDefault()

            # Define UI elements and their update methods
            ui_elements = [
                (self.window.column_order_combo, lambda: self.window.config_mgr.getConfigKeyColumnOrder()),
                (self.window.get_records_combo, lambda: RECORD_TYPE_ITEMS[RECORD_TYPE_CONFIG.index(
                    self.window.config_mgr.getConfigKeyGetRecordsAs() or RECORD_TYPE_CONFIG[0])]),
                (self.window.save_type_combo, lambda: self.window.config_mgr.getConfigKeyTableFormat()),
                (self.window.save_path_edit, lambda: self.window.config_mgr.getConfigKeyTableSavePath() or ""),
                 (self.window.fetch_squads_db_cb, lambda: self.window.config_mgr.getConfigKeyFetchSquadsDB()),
                (self.window.squad_folder_cb, lambda: self.window.config_mgr.getConfigKeySaveTablesInFolderUsingSquadFileName()),
            ]

            # Block signals, update UI, and re-enable signals properly
            for element, get_value in ui_elements:
                element.blockSignals(True)
                if isinstance(element, ComboBox):
                    element.setCurrentText(get_value())
                elif isinstance(element, LineEdit):
                    element.setText(get_value())
                elif isinstance(element, CheckBox):
                    element.setChecked(get_value())
                element.blockSignals(False)

            # Update reset button state after resetting
            self._update_reset_button_state()
            logger.info("Table settings reset to default values.")
        except Exception as e:
            ErrorHandler.handleError(f"Failed to reset table settings: {str(e)}")

    def _update_reset_button_state(self) -> None:
        """Enable or disable the Reset button based on whether settings differ from defaults."""
        try:
            default_settings = self.window.config_mgr.getDefaultTableSettings()
            current_settings = {
                "ColumnOrder": self.window.config_mgr.getConfigKeyColumnOrder(),
                "GetRecordsAs": self.window.config_mgr.getConfigKeyGetRecordsAs() or RECORD_TYPE_CONFIG[0],
                "TableFormat": self.window.config_mgr.getConfigKeyTableFormat(),
                "TableSavePath": self.window.config_mgr.getConfigKeyTableSavePath() or "",
                "FetchSquadsDB": self.window.config_mgr.getConfigKeyFetchSquadsDB(),
                "SaveTablesInFolderUsingSquadFileName": self.window.config_mgr.getConfigKeySaveTablesInFolderUsingSquadFileName(),
                "SelectAllTables": self.window.config_mgr.getConfigKeySelectAllTables()
            }
            # comparing current settings with default settings
            settings_changed = any(
                current_settings[key] != default_settings.get(key)
                for key in default_settings
            )

            if "reset" in self.buttons:
                self.buttons["reset"].setEnabled(settings_changed)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update reset button state: {str(e)}")
            if "reset" in self.buttons:
                self.buttons["reset"].setEnabled(True)  # Enable the button in case of error

def main() -> int:
    """Application entry point."""
    try:
        app = QApplication(sys.argv)
        app.setStyleSheet(MainStyles())
        app.setWindowIcon(QIcon(ICON_PATH))
        setTheme(Theme.DARK)
        setThemeColor(THEME_COLOR)
        window = TableSettingsWindow()
        window.show()
        return app.exec()
    except Exception as e:
        ErrorHandler.handleError(f"Error in main: {str(e)}")
        return 1

if __name__ == "__main__":
    main()