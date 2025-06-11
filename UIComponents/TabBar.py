from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from qfluentwidgets import FluentIcon
from UIComponents.BarStyles import BarStyles
from UIComponents.TableManager import TitleUpdateTable, SquadsUpdatesTable, FutSquadsUpdatesTable
from Core.Logger import logger
from Core.Initializer import ErrorHandler

class TabBar:
    ICONS = {
        "TitleUpdates": FluentIcon.UPDATE,
        "SquadsUpdates": FluentIcon.PEOPLE,
        "FutSquadsUpdates": FluentIcon.PEOPLE,
    }
    TABLE_CLASSES = {
        "TitleUpdates": TitleUpdateTable,
        "SquadsUpdates": SquadsUpdatesTable,
        "FutSquadsUpdates": FutSquadsUpdatesTable,
    }
    TITLES = {
        "TitleUpdates": "Title Updates",
        "SquadsUpdates": "Squads Updates",
        "FutSquadsUpdates": "FUT Squads Updates",
    }

    def __init__(self, parent=None, game_content=None, config=None, game_manager=None):
        self.parent = parent
        self.game_content = game_content or {}
        self.config = config
        self.game_manager = game_manager
        self.TabBarContainer = None
        self.tab_content_container = None
        self.bar_styles = BarStyles()
        self.table_components = {}

    def create_TabBar(self):
        """Initialize and create the tab bar with all tabs."""
        try:
            self._setup_tab_bar()
            self.add_tabs()
        except Exception as e:
            ErrorHandler.handleError(f"Error creating TabBar: {e}")
            raise

    def _setup_tab_bar(self):
        self.TabBarContainer = QTabWidget(self.parent)
        self.tab_content_container = QWidget(self.parent)
        self.tab_content_layout = QVBoxLayout(self.tab_content_container)
        self.tab_content_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_content_layout.setSpacing(0)
        self.TabBarContainer.setStyleSheet(self.bar_styles)

    def add_tabs(self):
        """Add tabs without immediately updating tables."""
        for tab_key in self.game_manager.getTabKeys():
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            table_class = self.TABLE_CLASSES.get(tab_key)
            if table_class:
                table_component = self._init_tab(tab_key, table_class)
                layout.addWidget(table_component.table)
                self.TabBarContainer.addTab(widget, QIcon(self.ICONS[tab_key].icon()), self.TITLES.get(tab_key, tab_key))
            else:
                logger.warning(f"No table class for tab key: {tab_key}")

    def _init_tab(self, tab_key: str, table_class) -> any:
        """Initialize a specific tab with its table component."""
        profile_type = (
            self.game_manager.getProfileTypeTitleUpdate() if tab_key == self.game_manager.getTabKeyTitleUpdates()
            else self.game_manager.getProfileTypeSquad()
        )
        self.table_components[tab_key] = table_class(
            parent=self.parent,
            game_content=self.game_content,
            config=self.config,
            game_manager=self.game_manager,
            profile_type=profile_type,
            tab_key=tab_key
        )
        return self.table_components[tab_key]

    def get_table_component(self, tab_key: str = "TitleUpdates") -> any:
        return self.table_components.get(tab_key)

    def update_game_content(self, game_content):
        """Update game content for all tabs and refresh tables."""
        self.game_content = game_content or {}
        for key, component in self.table_components.items():
            profile_type, content_key = self.parent._get_tab_info(key)
            tab_content = self.game_content.get(profile_type, {}).get(content_key, [])
            component.game_content = {content_key: tab_content}
            component.update_table()
            logger.debug(f"Updated game content for tab: {key}")