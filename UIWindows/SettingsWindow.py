import sys, os, json, csv, io, datetime
from typing import List, Optional

from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget, 
                               QSizePolicy, QPushButton, QTabWidget, QSpacerItem, QButtonGroup,
                               QFileDialog, QMessageBox)
from PySide6.QtGui import QGuiApplication, QIcon, QColor, QDesktopServices
from PySide6.QtCore import Qt, QSize, Signal, QEvent, QTimer, QUrl
from qframelesswindow import AcrylicWindow
from qfluentwidgets import (Theme, setTheme, setThemeColor, FluentIcon, CheckBox, 
                            RadioButton, SimpleCardWidget, ComboBox, EditableComboBox, 
                            LineEdit, MessageBoxBase, SubtitleLabel, CaptionLabel, InfoBar, InfoBarPosition)

from UIComponents.Personalization import AcrylicEffect
from UIComponents.Tooltips import apply_tooltip
from UIComponents.MainStyles import MainStyles
from Core.Logger import logger
from Core.Initializer import ErrorHandler, GameManager, ConfigManager, NotificationHandler
from UIComponents.TitleBar import TitleBar
from UIComponents.MiniSpinner import MiniSpinnerForButton

# Constants for SettingsWindow
WINDOW_TITLE = "Settings"
WINDOW_SIZE = (720, 480)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/FRICON.png"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = True

# Unified styles
TITLE_STYLE = "font-weight: bold; color: white; font-size: 16px;"
DESC_STYLE = "color: rgba(255, 255, 255, 0.7); font-size: 12px;"
TEXT_STYLE = "background-color: transparent; color: white; font-size: 14px;"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"

TAB_BUTTON_STYLE = """
QPushButton {
    border-radius: 0px;
    border: none;
    background-color: transparent; 
    color: white;
    font-size: 14px;
    padding: 8px 10px;
    text-align: left;
}
QPushButton:hover {
    background-color: rgba(255, 255, 255, 0.02);
}
QPushButton:pressed, QPushButton:checked {
    background-color: rgba(255, 255, 255, 0.05);
}
"""

SUB_TAB_STYLE = """
QTabWidget::pane {
    border: none;
}
QTabBar::tab {
    background: transparent;
    color: white;
    font-size: 14px;
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    background: rgba(255, 255, 255, 0.05);
}
QTabBar::tab:hover {
    background: rgba(255, 255, 255, 0.02);
}
"""

class SpeedConverterDialog(MessageBoxBase):
    """ Speed Converter Dialog """
    def __init__(self, parent=None):
        super().__init__(parent)

        self.titleLabel = SubtitleLabel('MB to KB Converter', self)
        self.inputLabel = CaptionLabel("Enter speed in MB/s:")
        self.inputEdit = LineEdit(self)
        self.outputLabel = CaptionLabel("Speed in KB/s:")
        self.outputEdit = LineEdit(self)

        self.inputEdit.setPlaceholderText("e.g.: 2 or 2.5 or 2.63")
        self.outputEdit.setReadOnly(True)
        self.outputEdit.setPlaceholderText("Converted value")

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.inputLabel)
        self.viewLayout.addWidget(self.inputEdit)
        self.viewLayout.addWidget(self.outputLabel)
        self.viewLayout.addWidget(self.outputEdit)

        self.yesButton.setText('Copy')
        self.yesButton.setIcon(FluentIcon.COPY)
        self.cancelButton.setText('Close')

        self.widget.setMinimumWidth(350)

        self.inputEdit.textChanged.connect(self.update_output)
        self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self.copy_to_clipboard)

    def update_output(self, text):
        if not text.strip(): 
            self.outputEdit.setText("")
            return
        try:
            value = float(text.strip())
            result = value * 1024
            self.outputEdit.setText(f"{result:.0f}")
        except ValueError:
            self.outputEdit.setText("Invalid input")

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.outputEdit.text())

class SettingsWindow(AcrylicWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.button_manager = ButtonManager(self)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*WINDOW_SIZE)
        AcrylicEffect(self)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.current_tab = None
        self.current_sub_tab_widget = None
        self.game_manager = GameManager()
        self.config_mgr = ConfigManager()
        self.tab_config = {
            "Installation": {
                "icon": FluentIcon.FOLDER_ADD,
                "sub_tabs": [
                    {"name": "Installation Options", "content_func": self._create_install_options_sub_tab, "desc": 'Configure installation options for title and squad updates.<br><span style="color: rgba(255, 255, 0, 0.7);">(You can also control these options from the Installation Options button on the main window)</span>'}
                ]
            },
            "Download": {
                "icon": FluentIcon.DOWNLOAD,
                "sub_tabs": [
                    {"name": "Download Options", "content_func": self._create_download_options_sub_tab, "desc": "Configure download options."}
                ]
            },
            "Visual": {
                "icon": FluentIcon.VIEW,
                "sub_tabs": [
                    {"name": "Table Columns", "content_func": self._create_table_columns_sub_tab, "desc": "Select the columns you want to display in the tables for each tab."},
                    {"name": "Content Version Display", "content_func": self._create_content_version_display_sub_tab, "desc": "Choose how to display the version content in title bar for each tab."}
                ]
            },
            "Squads": {
                "icon": FluentIcon.PEOPLE,
                "sub_tabs": [
                    {"name": "Table Settings", "content_func": self._create_table_settings_sub_tab, "desc": "Configure how squad tables are processed and saved."},
                    {"name": "Changelog Settings", "content_func": self._create_changelog_settings_sub_tab, "desc": "Configure how changelogs are processed and saved."}
                ]
            }
        }
        self.setup_ui()

    def setup_ui(self) -> None:
        try:
            self._setup_title_bar()
            self._setup_tab_container()
            self._setup_buttons()
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

    def _setup_tab_container(self) -> None:
        tab_container_layout = QHBoxLayout()
        tab_container_layout.setContentsMargins(0, 0, 0, 0)
        tab_container_layout.setSpacing(0)

        self.tab_layout = QVBoxLayout()
        self.tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_layout.setSpacing(0)

        self.tabs = {}
        for tab_name, config in self.tab_config.items():
            tab_button = QPushButton(tab_name)
            tab_button.setStyleSheet(TAB_BUTTON_STYLE)
            tab_button.setCheckable(True)
            tab_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            tab_button.setIcon(config["icon"].icon(Theme.DARK))
            tab_button.setIconSize(QSize(16, 16))
            tab_button.clicked.connect(lambda checked, t=tab_name: self.switch_tab(t))
            self.tab_layout.addWidget(tab_button)
            self.tabs[tab_name] = tab_button
            if tab_name != list(self.tab_config.keys())[-1]:
                separator = self._create_separator(height=1)
                self.tab_layout.addWidget(separator)

        self.tab_layout.addStretch()
        tab_widget = QWidget()
        tab_widget.setLayout(self.tab_layout)
        tab_widget.setFixedWidth(130)

        separator = self._create_separator(width=1)
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(20, 5, 20, 20)
        self.content_layout.setSpacing(0)

        tab_container_layout.addWidget(tab_widget)
        tab_container_layout.addWidget(separator)
        tab_container_layout.addWidget(self.content_container)

        self.main_layout.addLayout(tab_container_layout)
        self.switch_tab(list(self.tab_config.keys())[0])

    def _setup_buttons(self) -> None:
        separator = self._create_separator(height=1)
        self.main_layout.addWidget(separator)
        button_container = self.button_manager.create_buttons()
        self.main_layout.addWidget(button_container if button_container else QWidget())

    def _create_separator(self, width=None, height=None) -> QWidget:
        separator = QWidget()
        separator.setStyleSheet(SEPARATOR_STYLE)
        if width is not None:
            separator.setFixedWidth(width)
        if height is not None:
            separator.setFixedHeight(height)
        return separator

    def switch_tab(self, tab_name: str) -> None:
        if self.current_tab == tab_name:
            self.tabs[tab_name].setChecked(True)
            return

        self.current_tab = tab_name

        for name, button in self.tabs.items():
            button.setChecked(name == tab_name)

        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                while child.layout().count():
                    sub_child = child.layout().takeAt(0)
                    if sub_child.widget():
                        sub_child.widget().deleteLater()

        sub_tabs = self.tab_config[tab_name]["sub_tabs"]
        self._setup_sub_tabs(sub_tabs)
        self.content_layout.addStretch()

    def _setup_sub_tabs(self, sub_tabs: list) -> None:
        self.sub_tab_content_container = QWidget()
        self.sub_tab_content_layout = QVBoxLayout(self.sub_tab_content_container)
        self.sub_tab_content_layout.setContentsMargins(0, 0, 0, 0)
        self.sub_tab_content_layout.setSpacing(2)

        sub_tab_widget = QTabWidget()
        sub_tab_widget.setStyleSheet(SUB_TAB_STYLE)
        self.sub_tab_content_layout.addWidget(sub_tab_widget)

        separator = self._create_separator(height=1)
        self.sub_tab_content_layout.addWidget(separator)

        for sub_tab in sub_tabs:
            content_widget = QWidget()
            sub_tab_widget.addTab(content_widget, sub_tab["name"])

        self.current_sub_tab_widget = sub_tab_widget
        self._update_sub_tab_content(0)
        sub_tab_widget.currentChanged.connect(self._update_sub_tab_content)

        self.content_layout.addWidget(self.sub_tab_content_container)

    def _update_sub_tab_content(self, index: int) -> None:
        if not self.current_sub_tab_widget:
            return

        while self.sub_tab_content_layout.count() > 2:
            child = self.sub_tab_content_layout.takeAt(2)
            if child.widget():
                child.widget().deleteLater()

        sub_tabs = self.tab_config[self.current_tab]["sub_tabs"]
        current_sub_tab = sub_tabs[index]

        desc = QLabel(current_sub_tab["desc"])
        desc.setStyleSheet(DESC_STYLE)
        self.sub_tab_content_layout.addWidget(desc)

        self.sub_tab_content_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

        content_widget = current_sub_tab["content_func"]()
        self.sub_tab_content_layout.addWidget(content_widget)

        # Add Reset All button for the sub-tab
        reset_button = QPushButton(f"Reset All {current_sub_tab['name']}")
        reset_button.clicked.connect(lambda: self._reset_sub_tab(current_sub_tab["name"]))
        self.sub_tab_content_layout.addWidget(reset_button)
        self.sub_tab_content_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.sub_tab_content_layout.addStretch()

    def _reset_sub_tab(self, sub_tab_name: str) -> None:
        """Reset settings for a specific sub-tab."""
        try:
            reset_actions = {
                ("Installation", "Installation Options"): self.config_mgr.resetInstallationOptions,
                ("Download", "Download Options"): self.config_mgr.resetDownloadOptions,
                ("Visual", "Table Columns"): lambda: self.config_mgr.resetVisual("TableColumns"),
                ("Visual", "Content Version Display"): lambda: self.config_mgr.resetVisual("ContentVersionDisplay"),
                ("Squads", "Table Settings"): self.config_mgr.resetTableSettingsToDefault,
                ("Squads", "Changelog Settings"): self.config_mgr.resetChangelogSettings
            }

            if (self.current_tab, sub_tab_name) in reset_actions:
                reset_actions[(self.current_tab, sub_tab_name)]()
                InfoBar.success(
                    title="Success",
                    content=f"{sub_tab_name} have been reset to default.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )

                # Ensure the columns are updated immediately after the reset
                if sub_tab_name == "Table Columns":
                    self._update_table_columns(self.current_tab, sub_tab_name, True)

                # Refresh the current sub-tab content
                self._update_sub_tab_content(self.current_sub_tab_widget.currentIndex())
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting {sub_tab_name} settings: {e}")

    def _create_install_options_sub_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = SimpleCardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        # Backup settings folder
        backup_settings_cb = CheckBox("Backup \"settings\" folder for your game before install any title/squads update")
        backup_settings_cb.setStyleSheet(TEXT_STYLE)
        backup_settings_cb.setChecked(self.config_mgr.getConfigKeyBackupGameSettingsFolder())
        backup_settings_cb.stateChanged.connect(lambda state: self.config_mgr.setConfigKeyBackupGameSettingsFolder(state == Qt.CheckState.Checked.value))
        apply_tooltip(backup_settings_cb, "backupSettingsGameFolder")

        # Backup title update
        backup_tu_cb = CheckBox("Backup \"current\" title update before install the other one")
        backup_tu_cb.setStyleSheet(TEXT_STYLE)
        backup_tu_cb.setChecked(self.config_mgr.getConfigKeyBackupTitleUpdate())
        backup_tu_cb.stateChanged.connect(lambda state: self.config_mgr.setConfigKeyBackupTitleUpdate(state == Qt.CheckState.Checked.value))
        apply_tooltip(backup_tu_cb, "backupCurrentTU")

        # Delete title update
        delete_tu_cb = CheckBox("Delete \"Title Update\" from profile folder once installed")
        delete_tu_cb.setStyleSheet(TEXT_STYLE)
        delete_tu_cb.setChecked(self.config_mgr.getConfigKeyDeleteStoredTitleUpdate())
        delete_tu_cb.stateChanged.connect(lambda state: self.config_mgr.setConfigKeyDeleteStoredTitleUpdate(state == Qt.CheckState.Checked.value))
        apply_tooltip(delete_tu_cb, "deleteTUAfterInatall")

        # Delete squads
        delete_squads_cb = CheckBox("Delete \"Squad File\" from profile folder once installed")
        delete_squads_cb.setStyleSheet(TEXT_STYLE)
        delete_squads_cb.setChecked(self.config_mgr.getConfigKeyDeleteSquadsAfterInstall())
        delete_squads_cb.stateChanged.connect(lambda state: self.config_mgr.setConfigKeyDeleteSquadsAfterInstall(state == Qt.CheckState.Checked.value))
        apply_tooltip(delete_squads_cb, "deleteSquadsAfterInatall")
        
        # Delete live tuning update
        delete_live_container = QWidget()
        delete_live_layout = QHBoxLayout(delete_live_container)
        delete_live_layout.setContentsMargins(0, 0, 0, 0)
        delete_live_layout.setSpacing(0)

        delete_live_cb = CheckBox("Delete \"Live Tuning Update\" after rolling back your title update")
        delete_live_cb.setStyleSheet(TEXT_STYLE)
        delete_live_cb.setChecked(self.config_mgr.getConfigKeyDeleteLiveTuningUpdate())
        delete_live_cb.stateChanged.connect(lambda state: self.config_mgr.setConfigKeyDeleteLiveTuningUpdate(state == Qt.CheckState.Checked.value))
        apply_tooltip(delete_live_cb, "deleteLiveTuningUpdate")
        delete_live_layout.addWidget(delete_live_cb)
        delete_live_layout.addStretch()

        delete_now_btn = QPushButton(" Delete")
        delete_now_btn.setIcon(FluentIcon.DELETE.icon(Theme.DARK))
        delete_now_btn.setStyleSheet("border-top-right-radius: 0px; border-bottom-right-radius: 0px;")
        apply_tooltip(delete_now_btn, "deleteLiveTuningNow")

        folder_btn = QPushButton()
        folder_btn.setIcon(FluentIcon.FOLDER.icon(Theme.DARK))
        folder_btn.setStyleSheet("""
            QPushButton {
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-left: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        folder_btn.setFixedSize(28, 28)
        apply_tooltip(folder_btn, "openLiveTuningFolder")

        def delete_live_tuning():
            try:
                game_path = self.config_mgr.getConfigKeySelectedGame()
                if not game_path:
                    NotificationHandler.showWarning("No game selected. Please select a game first.")
                    return

                game_version = self.game_manager.getShortGameName(game_path).replace(self.game_manager.GAME_PREFIX, "")
                game_name = f"EA SPORTS FC {game_version}"
                live_tuning_base = self.game_manager.GAME_PATHS.get(f"{self.game_manager.GAME_PREFIX}{game_version}", {}).get("LiveTuningBase")
                if not live_tuning_base:
                    NotificationHandler.showWarning(f"Live Tuning Update path not configured for {game_name}.")
                    return

                live_tuning_path = os.path.expandvars(live_tuning_base)
                live_tuning_file = os.path.join(live_tuning_path, "onlinecache0", "atribbdb.bin")
                
                if not os.path.exists(live_tuning_file):
                    NotificationHandler.showInfo(
                        f"No Live Tuning Update found for {game_name}. "
                        "Your game is already free of live updates."
                    )
                    return

                try:
                    file_mtime = os.path.getmtime(live_tuning_file)
                    file_date = datetime.datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    os.remove(live_tuning_file)
                    message = (
                        f"The Live Tuning Update for {game_name} has been successfully removed.\n"
                        f"File: atribbdb.bin\n"
                        f"Last modified: {file_date}\n\n"
                        "Note: Connecting to EA servers will automatically re-download the live update."
                    )
                    NotificationHandler.showInfo(message)
                except Exception as e:
                    logger.error(f"Failed to delete {live_tuning_file}: {e}")
                    NotificationHandler.showWarning(f"Failed to delete Live Tuning Update for {game_name}: {str(e)}")

            except Exception as e:
                ErrorHandler.handleError(f"Failed to delete Live Tuning Update: {e}")

        def open_live_tuning_folder():
            try:
                game_path = self.config_mgr.getConfigKeySelectedGame()
                if not game_path:
                    NotificationHandler.showWarning("No game selected. Please select a game first.")
                    return

                game_version = self.game_manager.getShortGameName(game_path).replace(self.game_manager.GAME_PREFIX, "")
                live_tuning_base = self.game_manager.GAME_PATHS.get(f"{self.game_manager.GAME_PREFIX}{game_version}", {}).get("LiveTuningBase")
                if not live_tuning_base:
                    NotificationHandler.showWarning(f"Live Tuning Update path not configured for EA SPORTS FC {game_version}.")
                    return

                live_tuning_path = os.path.expandvars(os.path.join(live_tuning_base, "onlinecache0"))
                if not os.path.exists(live_tuning_path):
                    os.makedirs(live_tuning_path, exist_ok=True)
                QDesktopServices.openUrl(QUrl.fromLocalFile(live_tuning_path))

            except Exception as e:
                ErrorHandler.handleError(f"Failed to open Live Tuning Update folder: {e}")

        delete_now_btn.clicked.connect(delete_live_tuning)
        folder_btn.clicked.connect(open_live_tuning_folder)

        delete_live_layout.addWidget(delete_now_btn)
        delete_live_layout.addWidget(folder_btn)

        card_layout.addWidget(backup_settings_cb)
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        card_layout.addWidget(backup_tu_cb)
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        card_layout.addWidget(delete_tu_cb)
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)
        
        card_layout.addWidget(delete_squads_cb)
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)
        
        card_layout.addWidget(delete_live_container)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _create_download_options_sub_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = SimpleCardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        # Segments
        segments_container = QWidget()
        segments_layout = QHBoxLayout(segments_container)
        segments_layout.setContentsMargins(0, 0, 0, 0)
        segments_layout.setSpacing(0)

        segments_label = QLabel("Segments (Default: 8)")
        segments_label.setStyleSheet(TEXT_STYLE)
        apply_tooltip(segments_label, "segmentsOptions")

        segments_combo = EditableComboBox()
        segments_combo.addItems(["2", "3", "4", "5", "6", "8", "10", "16"])
        segments_combo.setCurrentText(self.config_mgr.getConfigKeySegments())
        segments_combo.setFixedSize(300, 28)
        segments_combo.currentTextChanged.connect(lambda text: self.config_mgr.setConfigKeySegments(text))

        segments_layout.addWidget(segments_label)
        segments_layout.addStretch()
        segments_layout.addWidget(segments_combo)

        card_layout.addWidget(segments_container)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Speed Limit
        speed_limit_container = QWidget()
        speed_limit_layout = QHBoxLayout(speed_limit_container)
        speed_limit_layout.setContentsMargins(0, 0, 0, 0)
        speed_limit_layout.setSpacing(10)

        speed_limit_cb = CheckBox("Speed Limit")
        speed_limit_cb.setStyleSheet(TEXT_STYLE)
        apply_tooltip(speed_limit_cb, "speedLimitOptions")

        speed_limit_edit = LineEdit()
        speed_limit_edit.setPlaceholderText("KB value e.g.: 1024")
        speed_limit_edit.setClearButtonEnabled(True)
        speed_limit_edit.setFixedSize(175, 28)
        speed_limit_edit.setText(self.config_mgr.getConfigKeySpeedLimit() or "")
        speed_limit_edit.textChanged.connect(lambda text: self.config_mgr.setConfigKeySpeedLimit(text if text.strip() else None))

        converter_button = QPushButton("MB to KB Converter")

        def toggle_speed_limit_input(state):
            is_enabled = state == Qt.CheckState.Checked.value
            speed_limit_edit.setEnabled(is_enabled)
            converter_button.setEnabled(is_enabled)
            self.config_mgr.setConfigKeySpeedLimitEnabled(is_enabled)
            if not is_enabled:
                speed_limit_edit.clear()
                self.config_mgr.setConfigKeySpeedLimit(None)

        speed_limit_cb.stateChanged.connect(toggle_speed_limit_input)
        converter_button.clicked.connect(lambda: SpeedConverterDialog(self).exec())

        speed_limit_layout.addWidget(speed_limit_cb)
        speed_limit_layout.addStretch()
        speed_limit_layout.addWidget(speed_limit_edit)
        speed_limit_layout.addWidget(converter_button)

        card_layout.addWidget(speed_limit_container)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Use IDM
        idm_container = QWidget()
        idm_layout = QVBoxLayout(idm_container)
        idm_layout.setContentsMargins(0, 0, 0, 0)
        idm_layout.setSpacing(5)

        idm_cb_container = QWidget()
        idm_cb_layout = QHBoxLayout(idm_cb_container)
        idm_cb_layout.setContentsMargins(0, 0, 0, 0)
        idm_cb_layout.setSpacing(0)

        idm_cb = CheckBox("Auto-use installed IDM for handling downloads instead of aria2")
        idm_cb.setStyleSheet(TEXT_STYLE)
        idm_cb.setChecked(self.config_mgr.getConfigKeyAutoUseIDM())
        apply_tooltip(idm_cb, "autoUseIDM")

        changepath_btn = QPushButton("Change Path")
        changepath_btn.setStyleSheet("border-top-right-radius: 0px; border-bottom-right-radius: 0px;")
        changepath_btn.setFixedWidth(90)
        changepath_btn.setEnabled(idm_cb.isChecked())
        apply_tooltip(changepath_btn, "changeIDMPath")

        redetect_btn = QPushButton()
        redetect_btn.setIcon(FluentIcon.SYNC.icon(Theme.DARK))
        redetect_btn.setStyleSheet("""
            QPushButton {
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-left: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        redetect_btn.setFixedSize(28, 28)
        redetect_btn.setEnabled(idm_cb.isChecked())
        apply_tooltip(redetect_btn, "redetectIDMPath")

        idm_cb_layout.addWidget(idm_cb)
        idm_cb_layout.addStretch()
        idm_cb_layout.addWidget(changepath_btn)
        idm_cb_layout.addWidget(redetect_btn)

        path_label = QLabel(f"Path: {self.config_mgr.getConfigKeyIDMPath() or 'Not set'}")
        path_label.setStyleSheet(TEXT_STYLE)
        path_label.setVisible(idm_cb.isChecked())

        idm_layout.addWidget(idm_cb_container)
        idm_layout.addWidget(path_label)

        def update_idm_path_display(path: Optional[str]) -> None:
            path_label.setText(f"Path: {path or 'Not set'}")
            self.config_mgr.setConfigKeyIDMPath(path)
            path_label.setVisible(idm_cb.isChecked())

        def toggle_idm(state: int) -> None:
            is_enabled = state == Qt.CheckState.Checked.value
            self.config_mgr.setConfigKeyAutoUseIDM(is_enabled)
            changepath_btn.setEnabled(is_enabled)
            redetect_btn.setEnabled(is_enabled)
            path_label.setVisible(is_enabled)
            if is_enabled:
                idm_path = self.config_mgr.getIDMPathFromRegistry()
                update_idm_path_display(idm_path)
            else:
                update_idm_path_display(None)

        idm_cb.stateChanged.connect(toggle_idm)

        def redetect_idm_path() -> None:
            if idm_cb.isChecked():
                idm_path = self.config_mgr.getIDMPathFromRegistry()
                update_idm_path_display(idm_path)

        redetect_btn.clicked.connect(redetect_idm_path)

        def change_idm_path() -> None:
            from PySide6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                parent=self,
                caption="Select IDM Executable",
                dir=os.path.expanduser("~"),
                filter="Executable Files (*.exe)"
            )
            if file_path and os.path.exists(file_path):
                update_idm_path_display(file_path)

        changepath_btn.clicked.connect(change_idm_path)

        card_layout.addWidget(idm_container)

        layout.addWidget(card)
        layout.addStretch()
        return widget
            
    def _create_table_columns_sub_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = SimpleCardWidget()
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        tables = ["TitleUpdates", "SquadsUpdates", "FutSquadsUpdates"]

        for idx, table in enumerate(tables):
            section_layout = QVBoxLayout()
            section_layout.setSpacing(5)

            section_title = QLabel(table)
            section_title.setStyleSheet(TEXT_STYLE)
            section_layout.addWidget(section_title)

            separator = self._create_separator(height=1)
            section_layout.addWidget(separator)

            columns = self.game_manager.getAvailableColumnsForTable(table)
            selected_columns = self.config_mgr.getConfigKeyTableColumns(table)
            for column in columns:
                cb = CheckBox(column)
                cb.setStyleSheet(TEXT_STYLE)
                cb.setChecked(column in selected_columns)
                if column in ["Name", "Status"]:
                    cb.setChecked(True)
                    cb.setEnabled(False)
                else:
                    cb.stateChanged.connect(lambda state, c=column, t=table: self._update_table_columns(t, c, state == Qt.CheckState.Checked.value))
                section_layout.addWidget(cb)

            section_layout.addStretch()
            card_layout.addLayout(section_layout)

            if idx < len(tables) - 1:
                separator = self._create_separator(width=1)
                card_layout.addWidget(separator)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _update_table_columns(self, table: str, column: str, checked: bool) -> None:
        try:
            current_columns = self.config_mgr.getConfigKeyTableColumns(table)
            if checked and column not in current_columns:
                current_columns.append(column)
            elif not checked and column in current_columns:
                current_columns.remove(column)
            self.config_mgr.setConfigKeyTableColumns(table, current_columns)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update table columns for {table}: {e}")

    def _create_content_version_display_sub_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = SimpleCardWidget()
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        tables = ["TitleUpdates", "SquadsUpdates", "FutSquadsUpdates"]

        for idx, table in enumerate(tables):
            section_layout = QVBoxLayout()
            section_layout.setSpacing(5)

            section_title = QLabel(table)
            section_title.setStyleSheet(TEXT_STYLE)
            section_layout.addWidget(section_title)

            separator = self._create_separator(height=1)
            section_layout.addWidget(separator)

            version_by_number = RadioButton("Version by number")
            version_by_date = RadioButton("Version by date")
            version_by_number.setStyleSheet(TEXT_STYLE)
            version_by_date.setStyleSheet(TEXT_STYLE)

            button_group = QButtonGroup(self)
            button_group.addButton(version_by_number)
            button_group.addButton(version_by_date)
            button_group.setExclusive(True)

            current_display = self.config_mgr.getConfigKeyContentVersionDisplay(table)
            version_by_number.setChecked(current_display == "VersionByNumber")
            version_by_date.setChecked(current_display == "VersionByDate")

            version_by_number.toggled.connect(lambda checked, t=table: self.config_mgr.setConfigKeyContentVersionDisplay(t, "VersionByNumber") if checked else None)
            version_by_date.toggled.connect(lambda checked, t=table: self.config_mgr.setConfigKeyContentVersionDisplay(t, "VersionByDate") if checked else None)

            section_layout.addWidget(version_by_number)
            section_layout.addWidget(version_by_date)

            section_layout.addStretch()
            card_layout.addLayout(section_layout)

            if idx < len(tables) - 1:
                separator = self._create_separator(width=1)
                card_layout.addWidget(separator)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _create_appearance_settings_sub_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = SimpleCardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        window_effect_label = QLabel("Window Effect:")
        window_effect_label.setStyleSheet(TEXT_STYLE)
        card_layout.addWidget(window_effect_label)

        window_effect_combo = ComboBox()
        window_effect_combo.addItems(["Default", "Acrylic", "Mica"])
        window_effect_combo.setCurrentIndex(0)
        window_effect_combo.setStyleSheet(TEXT_STYLE + " text-align: left;")
        card_layout.addWidget(window_effect_combo)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _create_cache_options_sub_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = SimpleCardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        cache_container = QWidget()
        cache_layout = QHBoxLayout(cache_container)
        cache_layout.setContentsMargins(0, 0, 0, 0)
        cache_layout.setSpacing(0)

        cache_label = QLabel("Build Cache for Squads/FutSquads")
        cache_label.setStyleSheet(TEXT_STYLE)
        apply_tooltip(cache_label, "Placeholder")

        build_cache_btn = QPushButton("Build Cache")
        build_cache_btn.setStyleSheet("border-top-right-radius: 0px; border-bottom-right-radius: 0px;")
        build_cache_btn.setFixedWidth(90)
        apply_tooltip(build_cache_btn, "Placeholder")

        cache_status = MiniSpinnerForButton()
        cache_status.setFixedSize(28, 28)
        cache_status.setStyleSheet("border-top-left-radius: 0px; border-bottom-left-radius: 0px; border-left: 1px solid rgba(255, 255, 255, 0.1);")
        cache_status.setIcon(FluentIcon.INFO.icon(color=QColor("#FFFF00")))  # Default to out-of-date
        apply_tooltip(cache_status, "cacheOutOfDate")

        def update_cache_status():
            cache_status.setSpinnerVisible(True)
            cache_status.setIcon(QIcon())
            logger.info("Cache status update triggered")
            QTimer.singleShot(3000, lambda: (
                cache_status.setSpinnerVisible(False),
                cache_status.setIcon(FluentIcon.COMPLETED.icon(color=QColor("#00FF00"))),
                apply_tooltip(cache_status, "cacheUpToDate")
            ))

        build_cache_btn.clicked.connect(update_cache_status)
        cache_status.clicked.connect(update_cache_status)

        cache_layout.addWidget(cache_label)
        cache_layout.addStretch()
        cache_layout.addWidget(build_cache_btn)
        cache_layout.addWidget(cache_status)

        card_layout.addWidget(cache_container)
        card_layout.addStretch()

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _create_table_settings_sub_tab(self) -> QWidget:
        """Create the content for Table Settings sub-tab."""
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

        column_order_combo = ComboBox()
        column_order_combo.addItems(["AsRead", "BitOffset", "DbMeta"])
        column_order_combo.setCurrentText(self.config_mgr.getConfigKeyColumnOrder())
        column_order_combo.setFixedSize(300, 28)
        column_order_combo.currentTextChanged.connect(
            lambda text: self.config_mgr.setConfigKeyColumnOrder(text)
        )
        apply_tooltip(column_order_combo, "columnOrderOptions")

        column_order_layout.addWidget(column_order_label)
        column_order_layout.addStretch()
        column_order_layout.addWidget(column_order_combo)

        card_layout.addWidget(column_order_container)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Get Records As
        get_records_container = QWidget()
        get_records_layout = QHBoxLayout(get_records_container)
        get_records_layout.setContentsMargins(0, 0, 0, 0)
        get_records_layout.setSpacing(0)

        get_records_label = QLabel("Get Records:")
        get_records_label.setStyleSheet(TEXT_STYLE)

        # Define mapping for display and config values
        RECORD_TYPE_ITEMS = ["Written Records Only", "Total Records"]
        RECORD_TYPE_CONFIG = ["WrittenRecords", "TotalRecords"]

        # Get current config value and map to display text
        get_records_as = self.config_mgr.getConfigKeyGetRecordsAs() or RECORD_TYPE_CONFIG[0]
        try:
            get_records_as_index = RECORD_TYPE_CONFIG.index(get_records_as)
            get_records_as_default = RECORD_TYPE_ITEMS[get_records_as_index]
        except ValueError:
            get_records_as_default = RECORD_TYPE_ITEMS[0]

        get_records_combo = ComboBox()
        get_records_combo.addItems(RECORD_TYPE_ITEMS)
        get_records_combo.setCurrentText(get_records_as_default)
        get_records_combo.setFixedSize(300, 28)
        get_records_combo.currentTextChanged.connect(
            lambda text: self.config_mgr.setConfigKeyGetRecordsAs(RECORD_TYPE_CONFIG[RECORD_TYPE_ITEMS.index(text)])
        )
        apply_tooltip(get_records_combo, "getRecordsOptions")  # Changed to match TableSettingsWindow

        get_records_layout.addWidget(get_records_label)
        get_records_layout.addStretch()
        get_records_layout.addWidget(get_records_combo)

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

        save_type_combo = ComboBox()
        save_type_combo.addItems([".csv", ".json", ".txt (UTF-8 BOM)", ".txt (UTF-16 LE)"])
        save_type_combo.setCurrentText(self.config_mgr.getConfigKeyTableFormat())
        save_type_combo.setFixedSize(300, 28)
        save_type_combo.currentTextChanged.connect(
            lambda text: self.config_mgr.setConfigKeyTableFormat(text)
        )
        apply_tooltip(save_type_combo, "saveTypeOptions")

        save_type_layout.addWidget(save_type_label)
        save_type_layout.addStretch()
        save_type_layout.addWidget(save_type_combo)

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
        top_layout.setContentsMargins(0, 0, 0, 5)
        top_layout.setSpacing(5)

        save_path_label = QLabel("Save Path:")
        save_path_label.setStyleSheet(TEXT_STYLE)

        browse_button = QPushButton("Browse")
        browse_button.setFixedSize(300, 28)
        browse_button.clicked.connect(
            lambda: self._browse_save_path(save_path_edit, "Select Table Save Path")
        )
        apply_tooltip(browse_button, "browseButton")

        top_layout.addWidget(save_path_label)
        top_layout.addStretch()
        top_layout.addWidget(browse_button)

        # Text field below
        save_path_edit = LineEdit()
        save_path_edit.setMinimumHeight(28)
        save_path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        save_path_edit.setPlaceholderText("Set path or leave it empty to be asked each time")
        save_path_edit.setText(self.config_mgr.getConfigKeyTableSavePath() or "")
        save_path_edit.textChanged.connect(
            lambda text: self.config_mgr.setConfigKeyTableSavePath(text if text.strip() else None)
        )

        save_path_layout.addWidget(top_row)
        save_path_layout.addWidget(save_path_edit)

        card_layout.addWidget(save_path_container)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Fetch Squads DB Checkbox
        fetch_squads_db_check = CheckBox("Fetch squads .db")
        fetch_squads_db_check.setStyleSheet(TEXT_STYLE)
        fetch_squads_db_check.setChecked(self.config_mgr.getConfigKeyFetchSquadsDB())
        fetch_squads_db_check.stateChanged.connect(
            lambda state: self.config_mgr.setConfigKeyFetchSquadsDB(state == Qt.CheckState.Checked.value)
        )

        card_layout.addWidget(fetch_squads_db_check)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Squad Folder Checkbox
        squad_folder_check = CheckBox("Save tables in a subfolder named using the squad file name")
        squad_folder_check.setStyleSheet(TEXT_STYLE)
        squad_folder_check.setChecked(self.config_mgr.getConfigKeySaveTablesInFolderUsingSquadFileName())
        squad_folder_check.stateChanged.connect(
            lambda state: self.config_mgr.setConfigKeySaveTablesInFolderUsingSquadFileName(state == Qt.CheckState.Checked.value)
        )

        card_layout.addWidget(squad_folder_check)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _create_changelog_settings_sub_tab(self) -> QWidget:
        """Create the content for Changelog Settings sub-tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = SimpleCardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        # Save As Type
        save_type_container = QWidget()
        save_type_layout = QHBoxLayout(save_type_container)
        save_type_layout.setContentsMargins(0, 0, 0, 0)
        save_type_layout.setSpacing(0)

        save_type_label = QLabel("Save As Type:")
        save_type_label.setStyleSheet(TEXT_STYLE)

        save_type_combo = ComboBox()
        save_type_combo.addItems([".xlsx", ".csv", ".json"])
        save_type_combo.setCurrentText(self.config_mgr.getConfigKeyChangelogFormat())
        save_type_combo.setFixedSize(300, 28)
        save_type_combo.currentTextChanged.connect(
            lambda text: self.config_mgr.setConfigKeyChangelogFormat(text)
        )
        apply_tooltip(save_type_combo, "saveTypeOptions")

        save_type_layout.addWidget(save_type_label)
        save_type_layout.addStretch()
        save_type_layout.addWidget(save_type_combo)

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
        top_layout.setContentsMargins(0, 0, 0, 5)
        top_layout.setSpacing(5)

        save_path_label = QLabel("Save Path:")
        save_path_label.setStyleSheet(TEXT_STYLE)

        browse_button = QPushButton("Browse")
        browse_button.setFixedSize(300, 28)
        browse_button.clicked.connect(
            lambda: self._browse_save_path(save_path_edit, "Select Changelog Save Path")
        )
        apply_tooltip(browse_button, "browseButton")

        top_layout.addWidget(save_path_label)
        top_layout.addStretch()
        top_layout.addWidget(browse_button)

        # Text field below
        save_path_edit = LineEdit()
        save_path_edit.setMinimumHeight(30)
        save_path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        save_path_edit.setPlaceholderText("Set path or leave it empty to be asked each time")
        save_path_edit.setText(self.config_mgr.getConfigKeyChangelogSavePath() or "")
        save_path_edit.textChanged.connect(
            lambda text: self.config_mgr.setConfigKeyChangelogSavePath(text if text.strip() else None)
        )

        save_path_layout.addWidget(top_row)
        save_path_layout.addWidget(save_path_edit)

        card_layout.addWidget(save_path_container)

        # Separator
        separator = self._create_separator(height=1)
        card_layout.addWidget(separator)

        # Squad Folder Checkbox
        squad_folder_check = CheckBox("Save changelogs in a subfolder named using the squad file name")
        squad_folder_check.setStyleSheet(TEXT_STYLE)
        squad_folder_check.setChecked(self.config_mgr.getConfigKeySaveChangelogsInFolderUsingSquadFileName())
        squad_folder_check.stateChanged.connect(
            lambda state: self.config_mgr.setConfigKeySaveChangelogsInFolderUsingSquadFileName(state == Qt.CheckState.Checked.value)
        )

        card_layout.addWidget(squad_folder_check)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _browse_save_path(self, line_edit: LineEdit, caption: str) -> None:
        """Open a folder dialog to select a save path and update the LineEdit."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            caption,
            line_edit.text() or os.path.expanduser("~")
        )
        if folder_path:
            line_edit.setText(folder_path)

class ButtonManager:
    def __init__(self, window: "SettingsWindow"):
        self.window = window
        self.button_container = None
        self.buttons = {}
        self.button_layout = None

    def create_buttons(self) -> QWidget:
        try:
            self._init_buttons()
            self._setup_layout()
            self.button_container = QWidget(self.window)
            self.button_container.setLayout(self.button_layout)
            return self.button_container
        except Exception as e:
            ErrorHandler.handleError(f"Error creating buttons: {e}")
            fallback_container = QWidget(self.window)
            fallback_layout = QHBoxLayout(fallback_container)
            fallback_layout.addStretch()
            logger.warning("Returning fallback button container due to error.")
            return fallback_container

    def _init_buttons(self) -> None:
        # Initialize buttons with updated names
        button_configs = {
            "cancel": "Cancel",
            "reset": "Reset All To Default",
            "done": "Done",
        }
        for name, text in button_configs.items():
            try:
                btn = QPushButton(text)
                btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed) 
                if name == "reset":
                    try:
                        apply_tooltip(btn, "ResetAllToDefault")
                    except Exception as e:
                        logger.warning(f"Failed to apply tooltip to {name} button: {e}")
                self.buttons[name] = btn
            except Exception as e:
                ErrorHandler.handleError(f"Error initializing button {name}: {e}")
                self.buttons[name] = QPushButton(f"{text} (Error)")

    def _setup_layout(self) -> None:
        self.button_layout = QHBoxLayout()
        self.buttons["cancel"].clicked.connect(self.window.close)
        self.buttons["reset"].clicked.connect(self.reset_all_to_default)
        self.button_layout.addWidget(self.buttons["cancel"])
        self.button_layout.addWidget(self.buttons["reset"])
        self.button_layout.addStretch()
        self.buttons["done"].clicked.connect(self.window.close)
        self.button_layout.addWidget(self.buttons["done"])
        
    def reset_all_to_default(self) -> None:
        """Reset all settings to their default values."""
        try:
            self.window.config_mgr.resetAllSettingsToDefault()
            InfoBar.success(
                title="Success",
                content="All settings have been reset to default.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self.window
            )
            # Refresh the current tab and its sub-tabs
            if self.window.current_tab:
                current_sub_tab_index = self.window.current_sub_tab_widget.currentIndex() if self.window.current_sub_tab_widget else 0
                # Clear the current content
                while self.window.content_layout.count():
                    child = self.window.content_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                # Rebuild the sub-tabs for the current tab
                sub_tabs = self.window.tab_config[self.window.current_tab]["sub_tabs"]
                self.window._setup_sub_tabs(sub_tabs)
                self.window.content_layout.addStretch()
                # Restore the sub-tab index
                if self.window.current_sub_tab_widget:
                    self.window.current_sub_tab_widget.setCurrentIndex(current_sub_tab_index)
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting all settings: {e}")
            
def main():
    try:
        app = QApplication(sys.argv)
        app.setStyleSheet(MainStyles())
        app.setWindowIcon(QIcon(ICON_PATH))
        setTheme(Theme.DARK)
        setThemeColor(THEME_COLOR)
        window = SettingsWindow()
        window.show()
        return app.exec()
    except Exception as e:
        ErrorHandler.handleError(f"Error in main: {e}")

if __name__ == "__main__":
    main()