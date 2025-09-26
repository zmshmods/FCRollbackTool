from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget, QApplication, QMenu, QFileDialog
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt, QPoint, QTimer

from UIComponents.BarStyles import BarStyles
from UIWindows.ImportTitleUpdateWindow import ImportTitleUpdateWindow
from MenuBar.File.OpenSquadFilesPath import open_squad_files_path
from MenuBar.File.OpenGameFolder import open_game_path
from MenuBar.File.OpenBackupsFolder import open_backups_path
from MenuBar.Tools.ClearEAAppCache import delete_cache_files
from MenuBar.Tools.RepairGame.Steam import SteamWindow
from MenuBar.Tools.RepairGame.EAApp import EAAppWindow
from MenuBar.Tools.RepairGame.EpicGames import EpicGamesWindow
from MenuBar.Tools.LiveEditorCompatibilityInfo import LiveEditorCompatibilityInfo
from MenuBar.Tools.ModsCompatibilityInfo import ModsCompatibilityInfo
from MenuBar.Help.InformationWindow import InformationWindow
from MenuBar.Help.ChangelogWindow import ChangelogWindow
from MenuBar.Help.OpenFAQs import open_faqs_url
from MenuBar.Help.OpenGuides import open_guides_url
from MenuBar.Help.OpenDiscord import open_discord_url

from Core.MainDataManager import MainDataManager
from Core.GameManager import GameManager
from Core.AppDataManager import AppDataManager
from Core.ErrorHandler import ErrorHandler

class MenuBar:
    ICONS = {
        "clear_cache": "Data/Assets/Icons/ic_fluent_broom_24_filled.png",
        "repair_game": "Data/Assets/Icons/ic_fluent_wrench_24_filled.png",
        "exit": "Data/Assets/Icons/ic_fluent_pane_close_24_filled.png",
        "steam": "Data/Assets/Icons/Steam.png",
        "ea_app": "Data/Assets/Icons/EA_Desktop.png",
        "epic_games": "Data/Assets/Icons/EpicGames.png",
        "info": "Data/Assets/Icons/ic_fluent_info_24_filled.png",
        "arrow_import": "Data/Assets/Icons/ic_fluent_arrow_import_24_filled.png",
        "folder_zip": "Data/Assets/Icons/ic_fluent_folder_zip_24_filled.png",
        "from_folder": "Data/Assets/Icons/ic_fluent_folder_24_filled.png",
        "open_folder": "Data/Assets/Icons/ic_fluent_open_folder_24_regular.png",
        "restart_app": "Data/Assets/Icons/ic_fluent_arrow_counterclockwise_dashes_24_filled.png",
        "code": "Data/Assets/Icons/ic_fluent_code_24_filled.png",
        "live_editor_compatibility": "Data/Assets/Icons/ic_fluent_comp_24_filled.png",
        "mods_compatibility": "Data/Assets/Icons/ic_fluent_shape_intersect_24_filled.png",
        "faqs": "Data/Assets/Icons/ic_fluent_chat_bubbles_question_24_filled.png",
        "guides":"Data/Assets/Icons/ic_fluent_book_search_24_filled.png",
        "discord":"Data/Assets/Icons/ic_discord_24_filled.png",

    }

    def __init__(self, parent=None):
        self.parent = parent
        self.MenuBarContainer = None
        self.FromBarStyles = BarStyles()
        self.game_mgr = GameManager()
        self.data_mgr = MainDataManager()
        self.app_data_mgr = AppDataManager()
        self.windows_list = []

    def create_button(self, text, menu_callback):
        button = QPushButton(text, self.parent)
        button.setFont(self.parent.font())
        button.setStyleSheet(self.FromBarStyles)
        button.clicked.connect(lambda: menu_callback(button))
        return button

    def create_menu(self, actions):
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.FromBarStyles)
        for action_data in actions:
            if action_data == "separator":
                menu.addSeparator()
            elif isinstance(action_data, dict):
                if "submenu" in action_data:
                    submenu = QMenu(action_data["text"], self.parent)
                    submenu.setStyleSheet(self.FromBarStyles)
                    submenu.setIcon(QIcon(self.ICONS[action_data["icon_key"]]))
                    for sub_action in action_data["submenu"]:
                        action = self._create_action(**sub_action)
                        submenu.addAction(action)
                    menu.addMenu(submenu)
                else:
                    action = self._create_action(**action_data)
                    menu.addAction(action)
        return menu

    def _create_action(self, text, icon_key, callback=None, shortcut=None):
        action = QAction(text, self.parent)
        action.setIcon(QIcon(self.ICONS[icon_key]))
        if callback:
            action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)
            self.parent.addAction(action)
        return action

    def create_MenuBar(self):
        try:
            self.MenuBarContainer = QWidget(self.parent)
            self.MenuBarContainer.setStyleSheet("background-color: rgba(10, 10, 10, 0.03);")
            self.MenuBarContainer.setFixedHeight(26)
            self.MenuBar = QHBoxLayout(self.MenuBarContainer)
            self.MenuBar.setContentsMargins(0, 0, 0, 0)
            self.MenuBar.setAlignment(Qt.AlignLeft)
            menus = [
                (" File ", self.FileMenu),
                (" Tools ", self.ToolsMenu),
                (" Help ", self.HelpMenu)
            ]
            for text, menu_callback in menus:
                self.MenuBar.addWidget(self.create_button(text, menu_callback))
            self.parent.main_layout.addWidget(self.MenuBarContainer)
        except Exception as e:
            ErrorHandler.handleError(f"Error creating MenuBar: {e}")

    def FileMenu(self, button):
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.FromBarStyles)
        import_submenu = QMenu("Import Title Update", self.parent)
        import_submenu.setStyleSheet(self.FromBarStyles)
        import_submenu.setIcon(QIcon(self.ICONS["arrow_import"]))
        import_submenu.addAction(self._create_action(
            "Compressed File (*.rar *.zip *.7z)",
            "folder_zip",
            self.select_compressed_file,
            "Ctrl+Shift+C"
        ))
        import_submenu.addAction(self._create_action(
            "Folder",
            "from_folder",
            self.select_folder,
            "Ctrl+Shift+F"
        ))
        menu.addMenu(import_submenu)
        menu.addAction(self._create_action("Open Game Folder", "open_folder", open_game_path, "Ctrl+G"))
        menu.addAction(self._create_action("Open Squad Files Path", "open_folder", open_squad_files_path))
        menu.addAction(self._create_action("Open Backups Folder", "open_folder", open_backups_path))
        menu.addSeparator()
        menu.addAction(self._create_action("Exit", "exit", QApplication.quit, "Alt+F4"))
        menu.exec(button.mapToGlobal(QPoint(button.rect().bottomLeft().x(), button.rect().bottomLeft().y())))

    def select_compressed_file(self):
        dialog = QFileDialog(self.parent)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("Compressed Files (*.zip *.rar *.7z)")
        if dialog.exec():
            input_paths = dialog.selectedFiles()
            for input_path in input_paths:
                self.show_window(lambda: ImportTitleUpdateWindow(input_path))

    def select_folder(self):
        dialog = QFileDialog(self.parent)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        if dialog.exec():
            folder = dialog.selectedFiles()[0]
            if folder:
                self.show_window(lambda: ImportTitleUpdateWindow(folder))

    def ToolsMenu(self, button):
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.FromBarStyles)
        repair_submenu = QMenu("Repair Game", self.parent)
        repair_submenu.setStyleSheet(self.FromBarStyles)
        repair_submenu.setIcon(QIcon(self.ICONS["repair_game"]))
        repair_submenu.addAction(self._create_action("Steam", "steam", lambda: self.show_window(SteamWindow)))
        repair_submenu.addAction(self._create_action("EA App", "ea_app", lambda: self.show_window(EAAppWindow)))
        repair_submenu.addAction(self._create_action("Epic Games", "epic_games", lambda: self.show_window(EpicGamesWindow)))
        menu.addMenu(repair_submenu)
        menu.addAction(self._create_action("Clear EA App Cache", "clear_cache", delete_cache_files))
        menu.addAction(self._create_action("Live Editor Compatibility Info", "live_editor_compatibility", lambda: self.show_window(LiveEditorCompatibilityInfo)))
        menu.addAction(self._create_action("Mods Compatibility Info", "mods_compatibility", lambda: self.show_window(ModsCompatibilityInfo)))
        menu.exec(button.mapToGlobal(QPoint(button.rect().bottomLeft().x(), button.rect().bottomLeft().y())))

    def HelpMenu(self, button):
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.FromBarStyles)
        menu.addAction(self._create_action("Information", "info", lambda: self.show_window(InformationWindow, isModal=True)))
        menu.addAction(self._create_action("Changelog", "code", lambda: self.show_window(ChangelogWindow, isModal=True)))
        menu.addAction(self._create_action("FAQs", "faqs", open_faqs_url))
        menu.addAction(self._create_action("Guides", "guides", open_guides_url))
        menu.addAction(self._create_action("Discord", "discord", open_discord_url))
        menu.exec(button.mapToGlobal(QPoint(button.rect().bottomLeft().x(), button.rect().bottomLeft().y())))

    def show_window(self, window_class, isModal=False):
        try:
            # Handle callable that returns a window instance
            if callable(window_class) and not isinstance(window_class, type):
                window = window_class()
            else:
                window = window_class()
            window.setWindowModality(Qt.ApplicationModal if isModal else Qt.NonModal)
            window.show()
            self.center_child_window(window)
            self.windows_list.append(window)
            self.parent.destroyed.connect(window.close)
        except Exception as e:
            ErrorHandler.handleError(f"Error opening window: {e}")

    def center_child_window(self, child_window):
        QApplication.processEvents()
        parent_geom = self.parent.geometry()
        child_geom = child_window.geometry()
        x = parent_geom.x() + (parent_geom.width() - child_geom.width()) // 2
        y = parent_geom.y() + (parent_geom.height() - child_geom.height()) // 2
        child_window.move(x, y)