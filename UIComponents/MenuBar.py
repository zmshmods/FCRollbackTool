import os, sys, subprocess, ctypes
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget, QApplication, QMenu, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt, QPoint
from MenuBar.File.ImportTitleUpdate import TitleUpdate
from MenuBar.File.OpenSquadFilesPath import OpenSquadFilesPath 
from MenuBar.File.OpenGameFolder import OpenGameFolder
from MenuBar.Tools.ClearEA_AppCache import delete_cache_files
from MenuBar.Tools.RepairGame.Steam import SteamWindow
from MenuBar.Tools.RepairGame.EAApp import EAAppWindow
from MenuBar.Tools.RepairGame.EpicGames import EpicGamesWindow
from MenuBar.Help.InformationWindow import InformationWindow
from MenuBar.Help.ChangelogWindow import ChangelogWindow
from UIWindows.TitleUpdateTable import TableWidgetComponent
from Core.Logger import logger
from UIComponents.ToolBoxMenuStyles import ToolBoxMenuStyles 

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
        "refresh_table": "Data/Assets/Icons/ic_fluent_arrow_sync_24_filled.png",
        "restart_app": "Data/Assets/Icons/ic_fluent_arrow_counterclockwise_dashes_24_filled.png",
        "code": "Data/Assets/Icons/ic_fluent_code_24_filled",

    }

    def __init__(self, parent=None):
        self.parent = parent
        self.MenuBarContainer = None
        self.FromToolBoxMenuStyles = ToolBoxMenuStyles()  # الحصول على الأنماط

    def create_button(self, text, menu_callback):
        button = QPushButton(text, self.parent)
        button.setFont(self.parent.font())
        button.setStyleSheet(self.FromToolBoxMenuStyles)
        button.clicked.connect(lambda: menu_callback(button))
        return button

    def create_menu(self, actions):
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.FromToolBoxMenuStyles)
        for action_data in actions:
            if action_data == "separator":
                menu.addSeparator()
            elif isinstance(action_data, dict):
                if "submenu" in action_data:
                    submenu = QMenu(action_data["text"], self.parent)
                    submenu.setStyleSheet(self.FromToolBoxMenuStyles)
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
        icon = QIcon(self.ICONS[icon_key])
        action.setIcon(icon)
        if callback:
            action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)
            self.parent.addAction(action)  # إضافة الإجراء إلى النافذة الرئيسية
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
            logger.error(f"Error creating MenuBar: {e}")

    def FileMenu(self, button):
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.FromToolBoxMenuStyles)

        # Submenu for Import Title Update
        import_submenu = QMenu("Import Title Update", self.parent)
        import_submenu.setStyleSheet(self.FromToolBoxMenuStyles)
        import_submenu.setIcon(QIcon(self.ICONS["arrow_import"]))
        import_submenu.addAction(self._create_action("Compressed File (*.rar *.zip *.7z)", "folder_zip", TitleUpdate.select_compressed_file, "Ctrl+Shift+C"))
        import_submenu.addAction(self._create_action("Folder", "from_folder", TitleUpdate.select_folder, "Ctrl+Shift+F"))
        menu.addMenu(import_submenu)

        menu.addAction(self._create_action("Open Game Folder", "open_folder", lambda: OpenGameFolder(self.parent).open_game_path(), "Ctrl+G"))
        menu.addAction(self._create_action("Open Squad Files Path", "open_folder", lambda: OpenSquadFilesPath(self.parent).open_squad_files_path()))
        menu.addAction(self._create_action("Refresh Table", "refresh_table", lambda: TableWidgetComponent(self.parent).update_table(), "Ctrl+R"))
        menu.addSeparator()
        # Add Restart Action
        menu.addAction(self._create_action(
            "Restart", 
            "restart_app", 
            lambda: (
                subprocess.Popen([executable_path] + sys.argv) 
                if os.path.exists(executable_path := os.path.join(os.path.dirname(os.path.abspath(__file__)), "FC Rollback Tool.exe")) 
                else subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Main.py")] + sys.argv),
                QApplication.quit()
            )
        ))
        # Add Exit Action
        menu.addAction(self._create_action("Exit", "exit", QApplication.quit, "Alt+F4"))

        menu.exec(button.mapToGlobal(QPoint(button.rect().bottomLeft().x(), button.rect().bottomLeft().y())))

    def ToolsMenu(self, button):
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.FromToolBoxMenuStyles)

        # Submenu for Repair Game
        repair_submenu = QMenu("Repair Game", self.parent)
        repair_submenu.setStyleSheet(self.FromToolBoxMenuStyles)
        repair_submenu.setIcon(QIcon(self.ICONS["repair_game"]))
        repair_submenu.addAction(self._create_action("Steam", "steam", lambda: self.show_modal_window(SteamWindow), "Shift+S"))
        repair_submenu.addAction(self._create_action("EA App", "ea_app", lambda: self.show_modal_window(EAAppWindow)))
        repair_submenu.addAction(self._create_action("Epic Games", "epic_games", lambda: self.show_modal_window(EpicGamesWindow)))
        menu.addMenu(repair_submenu)

        # Other actions
        menu.addAction(self._create_action("Clear EA App Cache", "clear_cache", delete_cache_files,))

        menu.exec(button.mapToGlobal(QPoint(button.rect().bottomLeft().x(), button.rect().bottomLeft().y())))

    def HelpMenu(self, button):
        menu = QMenu(self.parent)
        menu.setStyleSheet(self.FromToolBoxMenuStyles)
        menu.addAction(self._create_action("Information", "info", lambda: self.show_modal_window(InformationWindow)))
        menu.addAction(self._create_action("Changelog", "code", lambda: self.show_modal_window(ChangelogWindow)))
        menu.exec(button.mapToGlobal(QPoint(button.rect().bottomLeft().x(), button.rect().bottomLeft().y())))

    def show_modal_window(self, window_class):
        try:
            window = window_class()
            window.setWindowModality(Qt.ApplicationModal)
            window.show()
        except Exception as e:
            logger.error(f"Error opening window: {e}")
