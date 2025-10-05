import os
import sys
import webbrowser
from typing import Dict, List, Tuple, Optional
from PySide6.QtCore import QPoint, QSize, Qt, QSharedMemory, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon, QFont
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QMenu, QPushButton,
    QTabWidget, QVBoxLayout, QWidget, QWidgetAction, QFileDialog
)
from qfluentwidgets import CheckBox, FluentIcon, setTheme, setThemeColor, Theme, MessageBox

from UIComponents.BarStyles import BarStyles
from UIComponents.MainStyles import MainStyles
from UIComponents.MenuBar import MenuBar
from UIComponents.Personalization import BaseWindow
from Core.TableManager import (
    TitleUpdateTable, SquadsUpdatesTable, FutSquadsUpdatesTable
)
from UIComponents.TitleBar import TitleBar
from UIComponents.Tooltips import apply_tooltip
from UIWindows.DownloadWindow import DownloadWindow
from UIWindows.InstallWindow import InstallWindow
from UIWindows.SelectGameWindow import SelectGameWindow
from UIWindows.SettingsWindow import SettingsWindow
from UIWindows.SquadsTablesFetcherWindow import SquadsTablesFetcherWindow
from UIWindows.SquadsChangelogsFetcherWindow import SquadsChangelogsFetcherWindow
from UIWindows.ToolUpdaterWindow import ToolUpdaterWindow
from UIWindows.PatchNotesWindow import PatchNotesWindow
from UIWindows.FilesChangelogWindow import FilesChangelogWindow


from Core.Logger import logger
from Core.ToolUpdateManager import ToolUpdateManager
from Core.MainDataManager import MainDataManager
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.AppDataManager import AppDataManager
from Core.NotificationManager import NotificationHandler
from Core.ErrorHandler import ErrorHandler
from Core.GameLauncher import launch_game_threaded

# Constants
APP_NAME = "FC Rollback Tool"
VERSION = ToolUpdateManager().getToolVersion()
BUILD_VERSION = ToolUpdateManager().getToolBulidVersion()
WINDOW_TITLE = f"{APP_NAME} - v{VERSION} ({{}}) {{}}"
APP_ICON_PATH = "Data/Assets/Icons/FRICON.png"
THEME_COLOR = "#00FF00"
WINDOW_SIZE = (990, 640)
SHARED_MEMORY_KEY = "FCRollbackToolSharedMemory"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"
SPACER_WIDTH = 130
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = True
SHOW_MIN_BUTTON = True
SHOW_CLOSE_BUTTON = True

class MainWindow(BaseWindow):
    def __init__(self, config_manager: ConfigManager, game_manager: GameManager, game_content: Dict = None):
        super().__init__()
        self.config_manager = config_manager
        self.game_manager = game_manager
        self.game_content = game_content or {}
        self.main_container = None
        self.button_manager = None
        self.menu_bar = None
        self.resize(*WINDOW_SIZE)
        self.center_window()
        self.config_manager.register_config_updated_callback(self._on_config_updated)
        self.setup_ui()

    def closeEvent(self, event):
        try:
            if not self.main_container:
                raise AttributeError("main_container not initialized")
            self.config_manager.setConfigKeyLastUsedTab(
                self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            )
            if self.button_manager:
                for window_list in [
                    self.button_manager.tables_windows,
                    self.button_manager.changelogs_windows,
                    self.button_manager.download_windows,
                    self.button_manager.install_windows,
                    self.button_manager.patch_notes_windows
                ]:
                    for window in window_list:
                        if window and not window.isHidden():
                            window.close()
                    window_list.clear()
            if self.menu_bar:
                for window in self.menu_bar.windows_list:
                    if window and not window.isHidden():
                        window.close()
                self.menu_bar.windows_list.clear()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to handle close event: {str(e)}")
        super().closeEvent(event)

    def _on_config_updated(self, table: str):
        try:
            if not self.main_container:
                raise AttributeError("main_container not initialized")
            current_tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            if current_tab_key == table:
                self._load_content_for_tab(self.main_container.tab_container.currentIndex())
                logger.debug(f"Updated title bar for table {table} due to config change")
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update title bar on config change for table {table}: {str(e)}")

    def setup_ui(self):
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 0)
            self.main_layout.setSpacing(0)
            self.interface_container = QWidget(self)
            self.interface_layout = QVBoxLayout(self.interface_container)
            self.interface_layout.setContentsMargins(0, 0, 0, 0)
            self.interface_layout.setSpacing(0)
            self.title_bar = TitleBar(
                window=self, title=WINDOW_TITLE.format("N/A", ""),
                icon_path=APP_ICON_PATH, spacer_width=SPACER_WIDTH,
                buttons={
                    "launch_game": (
                        " Launch Game", "Data/Assets/Icons/ic_fluent_play_24_regular.png",
                        lambda: launch_game_threaded(self.config_manager, self.game_manager),
                        ""
                    )
                },
                show_max_button=SHOW_MAX_BUTTON, show_min_button=SHOW_MIN_BUTTON,
                show_close_button=SHOW_CLOSE_BUTTON, bar_height=BAR_HEIGHT
            )
            self.title_bar.create_title_bar()
            self.menu_bar = MenuBar(self)
            self.menu_bar.create_menu_bar()
            self.main_container = MainContainer(self.config_manager, self.game_manager)
            self.main_container.create_content_container()
            self.button_manager = ButtonManager(self.config_manager, self.game_manager, self.main_container, self)
            buttons_widget = self.button_manager.create_buttons()
            self.main_layout.addWidget(self.menu_bar.menu_bar_container)
            self.main_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))
            self.interface_layout.addWidget(self.main_container.content_container)
            if buttons_widget:
                self.interface_layout.addWidget(buttons_widget)
            self.main_layout.addWidget(self.interface_container)
            
            self.main_container.tab_container.currentChanged.connect(self.on_tab_changed)
            for component in self.main_container.table_components.values():
                if hasattr(component, 'table'):
                    component.table.selectionModel().currentRowChanged.connect(self.button_manager.button_states)
                    component.table_updated_signal.connect(
                        lambda comp=component: self.button_manager.button_states(
                            comp.table.selectionModel().currentIndex(), None
                        )
                    )

            self._load_content_for_selected_game()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to set up UI: {str(e)}")
            self.close()

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    @staticmethod
    def center_child_window(parent_window, child_window):
        QApplication.processEvents()
        parent_geom = parent_window.frameGeometry()
        child_geom = child_window.frameGeometry()
        x = parent_geom.x() + (parent_geom.width() - child_geom.width()) // 2
        y = parent_geom.y() + (parent_geom.height() - child_geom.height()) // 2
        child_window.move(x, y)

    def get_tab_info(self, tab_key: str) -> Tuple[str, str]:
        profile_type = self.game_manager.getProfileTypeTitleUpdate() if tab_key == self.game_manager.getTabKeyTitleUpdates() else self.game_manager.getProfileTypeSquad()
        content_key = {
            self.game_manager.getTabKeyTitleUpdates(): self.game_manager.getContentKeyTitleUpdate(),
            self.game_manager.getTabKeySquadsUpdates(): self.game_manager.getContentKeySquad(),
            self.game_manager.getTabKeyFutSquadsUpdates(): self.game_manager.getContentKeyFutSquad()
        }.get(tab_key)
        return profile_type, content_key

    def _load_content_for_selected_game(self):
        try:
            selected_game_path = self.config_manager.getConfigKeySelectedGame()
            if not selected_game_path or not os.path.exists(selected_game_path):
                raise ValueError("No valid game path selected")
            self.game_content = self.game_manager.loadGameContent(selected_game_path)
            if not self.game_content:
                raise ValueError("No game content available")
            tab_index = self.game_manager.getTabKeys().index(self.config_manager.getConfigKeyLastUsedTab()) if self.config_manager.getConfigKeyLastUsedTab() in self.game_manager.getTabKeys() else 0
            self.main_container.tab_container.setCurrentIndex(tab_index)
            self._load_content_for_tab(tab_index)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to load game content: {str(e)}")
            self.close()
            SelectGameWindow(ignore_selected_game=True).show()

    def _load_content_for_tab(self, tab_index: int):
        try:
            if not self.main_container:
                raise AttributeError("main_container not initialized")
            tab_key = self.game_manager.getTabKeys()[tab_index]
            profile_type, content_key = self.get_tab_info(tab_key)
            tab_content = self.game_content.get(profile_type, {}).get(content_key, [])
            version_key = self.config_manager.getContentVersionKey(tab_key)
            content_version = self.game_content.get(profile_type, {}).get(version_key, "N/A")
            if self.game_manager.is_offline:
                status_text = "<span style='color: red;'>" + content_version + " Offline lists</span>"
            else:
                status_text = "<span style='color: #00FF00;'>" + content_version + "</span>"
            self.title_bar.update_title(WINDOW_TITLE.format(status_text, ""))
            table_component = self.main_container.get_table_component(tab_key)
            if table_component:
                table_component.game_content = {content_key: tab_content}
                table_component.update_table()
                
                if hasattr(table_component, 'table'):
                    self.button_manager.button_states(table_component.table.selectionModel().currentIndex(), None)

            self.button_manager.update_button_visibility(tab_key)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to load content for tab {tab_key}: {str(e)}")

    def on_tab_changed(self, index: int):
        try:
            self._load_content_for_tab(index)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to change tab: {str(e)}")

class MainContainer:
    def __init__(self, config_manager: ConfigManager, game_manager: GameManager):
        self.config_manager = config_manager
        self.game_manager = game_manager
        self.tab_container = None
        self.table_components: Dict[str, QWidget] = {}
        self.content_container = None

    def create_content_container(self):
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.tab_container = QTabWidget()
        self.tab_container.setStyleSheet(BarStyles())
        tab_configs = {
            self.game_manager.getTabKeyTitleUpdates(): (TitleUpdateTable, FluentIcon.UPDATE, "Title Updates"),
            self.game_manager.getTabKeySquadsUpdates(): (SquadsUpdatesTable, FluentIcon.PEOPLE, "Squads Updates"),
            self.game_manager.getTabKeyFutSquadsUpdates(): (FutSquadsUpdatesTable, FluentIcon.PEOPLE, "FUT Squads Updates")
        }
        for tab_key, (table_class, icon, title) in tab_configs.items():
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            profile_type = self.game_manager.getProfileTypeTitleUpdate() if tab_key == self.game_manager.getTabKeyTitleUpdates() else self.game_manager.getProfileTypeSquad()
            self.table_components[tab_key] = table_class(
                game_content={}, config_manager=self.config_manager,
                game_manager=self.game_manager, profile_type=profile_type, tab_key=tab_key
            )
            layout.addWidget(self.table_components[tab_key].table)
            self.tab_container.addTab(widget, QIcon(icon.icon()), title)
        self.content_layout.addWidget(self.tab_container)

    def get_table_component(self, tab_key: str) -> Optional[QWidget]:
        return self.table_components.get(tab_key)

    def update_game_content(self, game_content: Dict):
        for tab_key, component in self.table_components.items():
            profile_type, content_key = self.main_window.get_tab_info(tab_key)
            tab_content = game_content.get(profile_type, {}).get(content_key, [])
            component.game_content = {content_key: tab_content}
            component.update_table()
            logger.debug(f"Updated game content for tab: {tab_key}")

class ButtonManager:
    def __init__(self, config_manager: ConfigManager, game_manager: GameManager, main_container: MainContainer, main_window: MainWindow):
        self.config_manager = config_manager
        self.game_manager = game_manager
        self.main_container = main_container
        self.main_window = main_window
        self.btn_container = None
        self.buttons: Dict[str, QPushButton] = {}
        self.tables_windows: List[QWidget] = []
        self.changelogs_windows: List[QWidget] = []
        self.download_windows: List[QWidget] = []
        self.install_windows: List[QWidget] = []
        self.patch_notes_windows: List[QWidget] = []
        self.files_changelog_windows: List[QWidget] = []

    def create_buttons(self):
        try:
            button_configs = {
                "settings": ("", FluentIcon.SETTING, self.open_settings, "settings_button"),
                "change_game": ("", FluentIcon.GAME, self.change_game, "change_game"),
                "open_profile": ("", FluentIcon.FOLDER, self.open_profile_folder, "open_profile_folder"),
                "uninstall": (" Uninstall", FluentIcon.DELETE, self.uninstall_installed_file, "uninstall_squad_button"),
                "install": (
                    " Install", FluentIcon.FOLDER_ADD, self.start_install, "install_button",
                    "border-top-right-radius: 0px; border-bottom-right-radius: 0px;"
                ),
                "install_options": (
                    "", FluentIcon.ARROW_DOWN, self.show_install_options, "install_options_button",
                    "QPushButton { border-top-left-radius: 0px; border-bottom-left-radius: 0px; border-left: 1px solid rgba(255, 255, 255, 0.1); }",
                    (28, 28), (12, 12)
                ),
                "fetch_tables": (" DB Tables", FluentIcon.DOCUMENT, self.open_tables, "fetch_tables_button"),
                "fetch_changelogs": (" Changelogs", FluentIcon.CALORIES, self.open_changelogs, "fetch_changelogs_button"),
                "download": (
                    " Download", FluentIcon.DOWNLOAD, self.start_download, "download_button",
                    "border-top-right-radius: 0px; border-bottom-right-radius: 0px;"
                ),
                "download_options": (
                    "", FluentIcon.ARROW_DOWN, self.show_download_options, "download_options_button",
                    "QPushButton { border-top-left-radius: 0px; border-bottom-left-radius: 0px; border-left: 1px solid rgba(255, 255, 255, 0.1); }",
                    (28, 28), (12, 12)
                ),
                "open_url": (" Open URL", FluentIcon.LINK, self.open_in_browser, "open_url_button"),
                "patch_notes": (
                    " Patch Notes", FluentIcon.CALORIES, self.patch_notes, "patch_notes_button",
                    "border-top-right-radius: 0px; border-bottom-right-radius: 0px;"
                ),
                "patch_notes_options": (
                    "", FluentIcon.LINK, self.open_patch_notes_url, "open_patch_notes_url_button",
                    "QPushButton { border-top-left-radius: 0px; border-bottom-left-radius: 0px; border-left: 1px solid rgba(255, 255, 255, 0.1); }",
                    (28, 28), (14, 14)
                ),
                "files_changelog": (
                    " Files Changelog", FluentIcon.HISTORY, self.open_files_changelog, "files_changelog_button"
                ),

            }

            for name, config in button_configs.items():
                btn = QPushButton(config[0])
                btn.setIcon(config[1].icon(Theme.DARK))
                btn.clicked.connect(config[2])
                apply_tooltip(btn, config[3])
                if len(config) > 4:
                    btn.setStyleSheet(config[4])
                    if len(config) > 5:
                        btn.setFixedSize(*config[5])
                        btn.setIconSize(QSize(*config[6]))
                self.buttons[name] = btn
                if name in ["download", "install", "install_options", "download_options", "patch_notes", "patch_notes_options", "uninstall"]:
                    btn.setEnabled(False)
            self._setup_button_layout()
            return self.btn_container
        except Exception as e:
            ErrorHandler.handleError(f"Failed to create buttons: {str(e)}")
            return None

    def _setup_button_layout(self):
        install_layout = QHBoxLayout()
        install_layout.setContentsMargins(0, 0, 0, 0)
        install_layout.setSpacing(0)
        install_layout.addWidget(self.buttons["install"])
        install_layout.addWidget(self.buttons["install_options"])

        download_layout = QHBoxLayout()
        download_layout.setContentsMargins(0, 0, 0, 0)
        download_layout.setSpacing(0)
        download_layout.addWidget(self.buttons["download"])
        download_layout.addWidget(self.buttons["download_options"])
        
        patch_notes_layout = QHBoxLayout()
        patch_notes_layout.setContentsMargins(0, 0, 0, 0)
        patch_notes_layout.setSpacing(0)
        patch_notes_layout.addWidget(self.buttons["patch_notes"])
        patch_notes_layout.addWidget(self.buttons["patch_notes_options"])

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 0, 10, 0)
        btn_layout.setSpacing(5)
        for btn_name in ["settings", "change_game", "open_profile"]:
            btn_layout.addWidget(self.buttons[btn_name])
        btn_layout.addStretch()
        btn_layout.addWidget(self.buttons["uninstall"])
        btn_layout.addLayout(install_layout)
        btn_layout.addLayout(download_layout)
        for btn_name in ["fetch_tables", "fetch_changelogs", "open_url"]:
            btn_layout.addWidget(self.buttons[btn_name])
        btn_layout.addLayout(patch_notes_layout)
        btn_layout.addWidget(self.buttons["files_changelog"])
        self.btn_container = QWidget(objectName="ButtonContainer", fixedHeight=45)
        self.btn_container.setLayout(btn_layout)

    def button_states(self, current, previous, deferred_call=False):
        if not deferred_call:
            QTimer.singleShot(0, lambda: self.button_states(current, previous, deferred_call=True))
            return

        try:
            action_buttons = ["download", "download_options", "install", "install_options", "uninstall",
                              "fetch_tables", "fetch_changelogs", "open_url", "patch_notes", "patch_notes_options", "files_changelog"]
            for btn_name in action_buttons:
                if btn_name in self.buttons:
                    self.buttons[btn_name].setEnabled(False)
            
            self.buttons["download"].setText(" Download")
            self.buttons["install"].setText(" Install")

            tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            table_component = self.main_container.get_table_component(tab_key)
            
            if not table_component or not hasattr(table_component, 'table') or not current.isValid() or current.row() < 0:
                self.update_button_visibility(tab_key)
                return

            table = table_component.table
            status_item = table.item(current.row(), table.columnCount() - 1)
            status_text = status_item.text() if status_item else ""
            status_mapping = getattr(table_component, 'STATUS_MAPPING', {})

            is_squads = tab_key in [self.game_manager.getTabKeySquadsUpdates(), self.game_manager.getTabKeyFutSquadsUpdates()]
            is_tu = tab_key == self.game_manager.getTabKeyTitleUpdates()
            
            self.buttons["fetch_tables"].setEnabled(is_squads)
            self.buttons["fetch_changelogs"].setEnabled(is_squads)
            self.buttons["open_url"].setEnabled(is_tu)
            self.buttons["patch_notes"].setEnabled(is_tu)
            self.buttons["patch_notes_options"].setEnabled(is_tu)
            self.buttons["files_changelog"].setEnabled(is_tu)

            if status_text == status_mapping.get("AvailableForDownload", {}).get("text", ""):
                self.buttons["download"].setEnabled(True)
                self.buttons["download_options"].setEnabled(True)

            elif status_text == status_mapping.get("Installed", {}).get("text", ""):
                self.buttons["download"].setEnabled(True)
                self.buttons["download_options"].setEnabled(True)
                self.buttons["download"].setText(" Re-Download")
                self.buttons["uninstall"].setEnabled(True)

                update_name = self.game_manager.getSelectedUpdate(tab_key, table_component)
                if update_name:
                    profile_files = table_component._get_profile_directories()
                    short_name = self.game_manager.getSelectedGameId(self.config_manager.getConfigKeySelectedGame()) or ""
                    normalized_files = {file.strip().lower() for file in profile_files.get(short_name, set())}
                    if table_component._is_update_available(update_name.strip().lower(), normalized_files):
                        self.buttons["install"].setText(" Re-Install")
                        self.buttons["install"].setEnabled(True)
                        self.buttons["install_options"].setEnabled(True)
                    else:
                        self.buttons["install"].setText(" Install")
                        self.buttons["install"].setEnabled(False)
                        self.buttons["install_options"].setEnabled(False)

            elif status_text == status_mapping.get("ReadyToInstall", {}).get("text", ""):
                self.buttons["download"].setEnabled(True)
                self.buttons["download_options"].setEnabled(True)
                self.buttons["download"].setText(" Re-Download")
                self.buttons["install"].setEnabled(True)
                self.buttons["install_options"].setEnabled(True)
            
            elif status_text in [status_mapping.get("ComingInConfirmed", {}).get("text", ""),
                                 status_mapping.get("NotAddedToList", {}).get("text", "")]:
                self.buttons["fetch_tables"].setEnabled(False)
                self.buttons["fetch_changelogs"].setEnabled(False)
                self.buttons["open_url"].setEnabled(False)

            self.update_button_visibility(tab_key)

        except Exception as e:
            ErrorHandler.handleError(f"Failed to update buttons: {str(e)}")

    def update_button_visibility(self, tab_key: str):
        try:
            visibility = {
                "uninstall": tab_key in [self.game_manager.getTabKeySquadsUpdates(), self.game_manager.getTabKeyFutSquadsUpdates()],
                "patch_notes": tab_key == self.game_manager.getTabKeyTitleUpdates(),
                "patch_notes_options": tab_key == self.game_manager.getTabKeyTitleUpdates(),
                "open_url": tab_key == self.game_manager.getTabKeyTitleUpdates(),
                "fetch_tables": tab_key in [self.game_manager.getTabKeySquadsUpdates(), self.game_manager.getTabKeyFutSquadsUpdates()],
                "fetch_changelogs": tab_key in [self.game_manager.getTabKeySquadsUpdates(), self.game_manager.getTabKeyFutSquadsUpdates()],
                "files_changelog": tab_key == self.game_manager.getTabKeyTitleUpdates(),
            }

            for btn_name, visible in visibility.items():
                self.buttons[btn_name].setVisible(visible)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update button visibility: {str(e)}")

    def _open_child_window(self, window_class, args: Tuple, window_list: List[QWidget]):
        try:
            tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            table = self.main_container.get_table_component(tab_key)
            if not table:
                raise ValueError("No table component for the selected tab")
            update_name = self.game_manager.getSelectedUpdate(tab_key, table)
            if not update_name:
                raise ValueError("No update selected")
            content_key = self.game_manager.getContentKeySquad() if tab_key == self.game_manager.getTabKeySquadsUpdates() else self.game_manager.getContentKeyFutSquad()
            updates = self.game_manager.getUpdatesList(
                table.game_content,
                profile_type=self.game_manager.getProfileTypeSquad()
            )
            row = table.table.currentRow()
            if row < 0:
                raise ValueError("No row selected")
            index_url = updates[content_key][row].get(self.game_manager.getDownloadURLKeyForTab(tab_key))
            if not index_url:
                raise ValueError("No Index URL available")
            update_name = updates[content_key][row].get(self.game_manager.getSquadsNameKey())
            released_date = updates[content_key][row].get(self.game_manager.getSquadsReleasedDateKey())
            window_instance = window_class(index_url=index_url, update_name=update_name, released_date=released_date, *args)
            window_list.append(window_instance)
            window_instance.show()
            MainWindow.center_child_window(self.main_window, window_instance)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to open child window: {str(e)}")

    def open_tables(self):
        self._open_child_window(SquadsTablesFetcherWindow, (), self.tables_windows)

    def open_changelogs(self):
        self._open_child_window(SquadsChangelogsFetcherWindow, (), self.changelogs_windows)

    def open_files_changelog(self):
        try:
            tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            table_component = self.main_container.get_table_component(tab_key)
            if not table_component:
                raise ValueError("No table component found for the current tab.")

            selected_row = table_component.table.currentRow()
            if selected_row < 0:
                return

            profile_type, _ = self.main_window.get_tab_info(tab_key)
            game_content_for_profile = self.main_window.game_content.get(profile_type, {})
            
            main_depot_id = game_content_for_profile.get(self.game_manager.getTitleUpdateMainDepotIDKey())
            eng_us_depot_id = game_content_for_profile.get(self.game_manager.getTitleUpdateEngUsDepotIDKey())
            
            updates = game_content_for_profile.get(self.game_manager.getContentKeyTitleUpdate(), [])
            if not updates or selected_row >= len(updates):
                raise ValueError("Update list is invalid or row is out of bounds.")
            
            update_item = updates[selected_row]
            main_manifest_id = update_item.get(self.game_manager.getTitleUpdateMainManifestIDKey())
            eng_us_manifest_id = update_item.get(self.game_manager.getTitleUpdateEngUsManifestIDKey())
            
            if not main_manifest_id:
                ErrorHandler.handleError("No Manifest ID found for this update.")
                return

            game_id = self.game_manager.getSelectedGameId(self.config_manager.getConfigKeySelectedGame())
            
            game_root_path = self.config_manager.getConfigKeySelectedGame()
            if not game_root_path:
                ErrorHandler.handleError("Could not determine the selected game path.")
                return

            changelog_window = FilesChangelogWindow(
                game_manager=self.game_manager,
                game_root_path=game_root_path,
                game_id=game_id,
                main_depot_id=main_depot_id,
                eng_us_depot_id=eng_us_depot_id,
                main_manifest_id=main_manifest_id,
                eng_us_manifest_id=eng_us_manifest_id,
                update_name=update_item.get(self.game_manager.getTitleUpdateNameKey(), "Unknown Update")
            )
            
            self.files_changelog_windows.append(changelog_window)
            changelog_window.show()
            MainWindow.center_child_window(self.main_window, changelog_window)

        except Exception as e:
            ErrorHandler.handleError(f"Failed to open depot changelog window: {str(e)}")

    def patch_notes(self):
        try:
            tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            table_component = self.main_container.get_table_component(tab_key)
            if not table_component:
                raise ValueError("No table component found for the current tab.")

            selected_row = table_component.table.currentRow()
            if selected_row < 0:
                return

            updates = self.game_manager.getUpdatesList(
                table_component.game_content,
                profile_type=self.game_manager.getProfileTypeTitleUpdate()
            )
            
            update_item = updates[self.game_manager.getContentKeyTitleUpdate()][selected_row]
            patch_notes_url = update_item.get(self.game_manager.getTitleUpdatePatchNotesKey())
            
            if not patch_notes_url:
                ErrorHandler.handleError("No Patch Notes URL found for this update.")
                return
            
            patch_notes_window = PatchNotesWindow(self.game_manager, patch_notes_url)
            self.patch_notes_windows.append(patch_notes_window)
            patch_notes_window.show()
            MainWindow.center_child_window(self.main_window, patch_notes_window)

        except Exception as e:
            ErrorHandler.handleError(f"Failed to open patch notes window: {str(e)}")

    def open_patch_notes_url(self):
        try:
            tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            table = self.main_container.get_table_component(tab_key)
            
            row = table.table.currentRow()
            if row < 0:
                raise ValueError("Invalid row selected")

            updates = self.game_manager.getUpdatesList(
                table.game_content,
                profile_type=self.game_manager.getProfileTypeTitleUpdate()
            )
            
            json_url = updates[self.game_manager.getContentKeyTitleUpdate()][row].get(self.game_manager.getTitleUpdatePatchNotesKey())
            if not json_url:
                raise ValueError("No patch notes JSON URL available")
            
            patch_data = self.game_manager.fetchPatchNotesData(json_url)
            if patch_data and (trello_url := patch_data.get("shortUrl")):
                webbrowser.open(trello_url)
            else:
                NotificationHandler.showWarning("Could not find the direct Trello link, opening the data URL instead.")
                webbrowser.open(json_url)

        except Exception as e:
            ErrorHandler.handleError(f"Failed to open patch notes URL: {str(e)}")

    def open_in_browser(self):
        try:
            tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            table = self.main_container.get_table_component(tab_key)
            updates = self.game_manager.getUpdatesList(
                table.game_content,
                profile_type=self.game_manager.getProfileTypeTitleUpdate()
            )
            row = table.table.currentRow()
            if row < 0 or row >= len(updates[self.game_manager.getContentKeyTitleUpdate()]):
                raise ValueError("Invalid row selected")
            url = updates[self.game_manager.getContentKeyTitleUpdate()][row].get(self.game_manager.getTitleUpdateDownloadURLKey())
            if not url:
                raise ValueError("No URL available")
            webbrowser.open(url)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to open URL: {str(e)}")

    def start_download(self):
        try:
            tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            table = self.main_container.get_table_component(tab_key)
            if not table:
                raise ValueError("No table component")

            update_name = self.game_manager.getSelectedUpdate(tab_key, table)
            if not update_name:
                raise ValueError("No update selected")

            content_key = {
                self.game_manager.getTabKeyTitleUpdates(): self.game_manager.getContentKeyTitleUpdate(),
                self.game_manager.getTabKeySquadsUpdates(): self.game_manager.getContentKeySquad(),
                self.game_manager.getTabKeyFutSquadsUpdates(): self.game_manager.getContentKeyFutSquad()
            }[tab_key]

            game_id = self.game_manager.getSelectedGameId(self.config_manager.getConfigKeySelectedGame())
            updates = self.game_manager.getUpdatesList(
                table.game_content,
                profile_type=self.game_manager.getProfileTypeTitleUpdate() if tab_key == self.game_manager.getTabKeyTitleUpdates() else self.game_manager.getProfileTypeSquad()
            )

            row = table.table.currentRow()
            if row < 0:
                raise ValueError("No row selected")

            index_url = updates[content_key][row].get(self.game_manager.getDownloadURLKeyForTab(tab_key))
            if not index_url:
                raise ValueError("No download URL")
            
            if tab_key == self.game_manager.getTabKeyTitleUpdates() and self.config_manager.getConfigKeyDownloadDisclaimer():
                message = (
                    "Downloading a large number of files in a short period of time may result in your IP address "
                    "being temporarily or permanently banned from MediaFire servers. You can also use the (Open URL) "
                    "button to manually download the files if you prefer.\n\nDo you want to proceed?"
                )
                msg_box = MessageBox("Download Disclaimer", message, self.main_window)
                msg_box.yesButton.setText("Proceed")
                msg_box.cancelButton.setText("Cancel")

                if not msg_box.exec():
                    return
                self.config_manager.setConfigKeyDownloadDisclaimer(False)

            download_window = DownloadWindow(update_name, index_url, game_id, tab_key)
            self.download_windows.append(download_window)
            download_window.show()
            MainWindow.center_child_window(self.main_window, download_window)

        except Exception as e:
            ErrorHandler.handleError(f"Failed to start download: {str(e)}")

    def start_install(self):
        try:
            tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            table = self.main_container.get_table_component(tab_key)
            if not table or not hasattr(table, 'table'):
                raise ValueError("Invalid table component")

            update_name = self.game_manager.getSelectedUpdate(tab_key, table)
            if not update_name:
                raise ValueError("No update selected")

            game_path = self.config_manager.getConfigKeySelectedGame()
            if not game_path:
                raise ValueError("No game path selected")

            profile_subfolder = {
                self.game_manager.getTabKeyTitleUpdates(): self.game_manager.getProfileTypeTitleUpdate(),
                self.game_manager.getTabKeySquadsUpdates(): os.path.join(self.game_manager.getProfileTypeSquad(), self.game_manager.getContentKeySquad()),
                self.game_manager.getTabKeyFutSquadsUpdates(): os.path.join(self.game_manager.getProfileTypeSquad(), self.game_manager.getContentKeyFutSquad())
            }.get(tab_key, "")

            profile_folder = self.game_manager.getProfileDirectory(self.game_manager.getSelectedGameId(game_path), profile_subfolder)
            file_path = os.path.join(profile_folder, update_name)

            for ext in MainDataManager().getCompressedFileExtensions() + [""]:
                if os.path.exists(test_path := os.path.join(profile_folder, update_name + ext)):
                    file_path = test_path
                    break
            else:
                raise ValueError(f"Update file not found: {file_path}")

            install_window = InstallWindow(update_name, tab_key, game_path, file_path, table_component=table)
            install_window.setWindowModality(Qt.ApplicationModal)
            self.install_windows.append(install_window)
            install_window.show()
            MainWindow.center_child_window(self.main_window, install_window)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to start installation of {update_name}: {str(e)}")

    def uninstall_installed_file(self):
        try:
            tab_key = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            table_component = self.main_container.get_table_component(tab_key)

            update_name = self.game_manager.getSelectedUpdate(tab_key, table_component)
            if not update_name:
                return

            settings_path = self.game_manager.getGameSettingsFolderPath(self.config_manager.getConfigKeySelectedGame())
            file_to_uninstall = os.path.join(settings_path, update_name)

            if os.path.exists(file_to_uninstall):
                os.remove(file_to_uninstall)
                logger.info(f"Successfully uninstall squads file: {file_to_uninstall}")
        
        except Exception as e:
            ErrorHandler.handleError(f"Failed to uninstall file: {str(e)}")

    def show_install_options(self):
        try:
            menu = QMenu()
            menu.setStyleSheet("QMenu { font-size: 12px; }")
            tab = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            options = [
                ("Backup \"settings\" folder for your game before install any title/squads update",
                 self.config_manager.getConfigKeyBackupGameSettingsFolder,
                 self.config_manager.setConfigKeyBackupGameSettingsFolder,
                 "backupSettingsGameFolder",
                 [self.game_manager.getTabKeyTitleUpdates(), self.game_manager.getTabKeySquadsUpdates(), self.game_manager.getTabKeyFutSquadsUpdates()]),
                ("Backup \"current\" title update before install the other one",
                 self.config_manager.getConfigKeyBackupTitleUpdate,
                 self.config_manager.setConfigKeyBackupTitleUpdate,
                 "backupCurrentTU",
                 [self.game_manager.getTabKeyTitleUpdates()]),
                ("Delete \"Title Update\" from profile folder once installed",
                 self.config_manager.getConfigKeyDeleteStoredTitleUpdate,
                 self.config_manager.setConfigKeyDeleteStoredTitleUpdate,
                 "deleteTUAfterInatall",
                 [self.game_manager.getTabKeyTitleUpdates()]),
                ("Delete \"Squad File\" from profile folder once installed",
                 self.config_manager.getConfigKeyDeleteSquadsAfterInstall,
                 self.config_manager.setConfigKeyDeleteSquadsAfterInstall,
                 "deleteSquadsAfterInatall",
                 [self.game_manager.getTabKeySquadsUpdates(), self.game_manager.getTabKeyFutSquadsUpdates()]),
                ("Delete \"Live Tuning Update\" after rolling back your title update",
                 self.config_manager.getConfigKeyDeleteLiveTuningUpdate,
                 self.config_manager.setConfigKeyDeleteLiveTuningUpdate,
                 "deleteLiveTuningUpdate",
                 [self.game_manager.getTabKeyTitleUpdates()])
            ]
            for text, get, set, tooltip, tabs in options:
                chk = CheckBox(text)
                chk.setTristate(False)
                chk.setChecked(get())
                color = 'white' if tab in tabs else 'rgba(255, 255, 255, 0.4)'
                chk.setStyleSheet(f"CheckBox {{ font-size: 12px; color: {color}; }}")
                chk.setEnabled(tab in tabs)
                chk.toggled.connect(lambda c, s=set: s(c))
                apply_tooltip(chk, tooltip)
                act = QWidgetAction(menu)
                act.setDefaultWidget(chk)
                menu.addAction(act)
            menu.exec(self.buttons["install_options"].mapToGlobal(QPoint(0, self.buttons["install_options"].height())))
        except Exception as e:
            ErrorHandler.handleError(f"Failed to show install options: {str(e)}")

    def show_download_options(self):
        try:
            menu = QMenu()
            menu.setStyleSheet("QMenu { font-size: 12px; }")
            chk = CheckBox("Auto-use installed IDM for handling downloads instead of aria2")
            chk.setTristate(False)
            chk.setChecked(self.config_manager.getConfigKeyAutoUseIDM())
            chk.setStyleSheet("CheckBox { font-size: 12px; color: white; }")

            def toggle_idm(checked):
                self.config_manager.setConfigKeyAutoUseIDM(checked)
                if checked:
                    idm_path = self.config_manager.getIDMPathFromRegistry()
                    if idm_path and os.path.exists(idm_path):
                        self.config_manager.setConfigKeyIDMPath(idm_path)
                    else:
                        file_path, _ = QFileDialog.getOpenFileName(
                            parent=None,
                            caption="Select IDM Executable",
                            dir=os.path.expanduser("~"),
                            filter="Executable Files (*.exe)"
                        )
                        if file_path and os.path.exists(file_path):
                            self.config_manager.setConfigKeyIDMPath(file_path)
                        else:
                            chk.setChecked(False)
                            self.config_manager.setConfigKeyAutoUseIDM(False)
                            NotificationHandler.showWarning("No valid IDM executable selected. IDM will not be used.")

            chk.toggled.connect(toggle_idm)
            apply_tooltip(chk, "autoUseIDM")
            act = QWidgetAction(menu)
            act.setDefaultWidget(chk)
            menu.addAction(act)
            menu.exec(self.buttons["download_options"].mapToGlobal(QPoint(0, self.buttons["download_options"].height())))
        except Exception as e:
            ErrorHandler.handleError(f"Failed to show download options: {str(e)}")

    def open_profile_folder(self):
        try:
            tab = self.game_manager.getTabKeys()[self.main_container.tab_container.currentIndex()]
            subfolder = {
                self.game_manager.getTabKeyTitleUpdates(): self.game_manager.getProfileTypeTitleUpdate(),
                self.game_manager.getTabKeySquadsUpdates(): os.path.join(self.game_manager.getProfileTypeSquad(), self.game_manager.getContentKeySquad()),
                self.game_manager.getTabKeyFutSquadsUpdates(): os.path.join(self.game_manager.getProfileTypeSquad(), self.game_manager.getContentKeyFutSquad())
            }.get(tab, self.game_manager.getProfileTypeSquad())

            game_id = self.game_manager.getSelectedGameId(self.config_manager.getConfigKeySelectedGame())
            if not game_id:
                ErrorHandler.handleError("Could not identify the selected game.")
                return

            dir_path = self.game_manager.getProfileDirectory(game_id, subfolder)
            QDesktopServices.openUrl(QUrl.fromLocalFile(dir_path))
        except Exception as e:
            ErrorHandler.handleError(f"Failed to open profile folder: {str(e)}")

    def change_game(self):
        try:
            QApplication.activeWindow().close()
            SelectGameWindow(ignore_selected_game=True).show()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to change game: {str(e)}")

    def open_settings(self):
        try:
            settings_window = SettingsWindow()
            settings_window.show()
            MainWindow.center_child_window(self.main_window, settings_window)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to open settings window: {str(e)}")

def main():
    main_data_manager = MainDataManager()
    logger.info(f"Starting {APP_NAME} v{VERSION} Build v{BUILD_VERSION} Launched From: {main_data_manager.application_path}")

    app = QApplication(sys.argv)
    # font = QFont("")
    # font.setPointSize(10)
    # app.setFont(font)
    app.setWindowIcon(QIcon(APP_ICON_PATH))
    if not QSharedMemory(SHARED_MEMORY_KEY).create(1):
        NotificationHandler.showWarning(f"{APP_NAME} is already running.")
        sys.exit()

    app.setStyleSheet(MainStyles())
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)

    app_data_manager = AppDataManager()

    update_window = ToolUpdaterWindow()
    update_window.setWindowModality(Qt.ApplicationModal)
    if update_window.run_check():
        app.exec()
        if update_window.isVisible():
            return

    main_window = SelectGameWindow()
    main_window.show()
    
    app.aboutToQuit.connect(lambda: app_data_manager.manageTempFolder(clean=True, clean_all=True))
    sys.exit(app.exec())

if __name__ == "__main__":
    main()