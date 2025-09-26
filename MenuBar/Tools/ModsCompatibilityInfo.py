import sys
from collections import deque
from typing import Optional, Dict, List
import webbrowser
import os
import subprocess
from urllib.parse import quote_plus

from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QSize, QRect
from PySide6.QtGui import (QIcon, QPixmap, QFont, QColor, QPalette, QFontMetrics, QPainter, QAction,
                           QPainterPath, QGuiApplication)
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QWidget, QLabel, QHBoxLayout, QFrame,
                                 QListWidgetItem, QPushButton, QFileDialog, QStackedWidget)

from qfluentwidgets import (ComboBox, ScrollArea, SimpleCardWidget, FluentIcon, Theme, setTheme,
                            setThemeColor, BodyLabel, CaptionLabel, setFont, InfoBadge, DotInfoBadge,
                            ListWidget, isDarkTheme, ListItemDelegate, RoundMenu, CheckBox)

from UIComponents.Personalization import BaseWindow
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.Spinner import LoadingSpinner
from UIComponents.Tooltips import apply_tooltip
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.ErrorHandler import ErrorHandler

TITLE = "Mods Compatibility Info"
WINDOW_SIZE = (990, 640)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/ic_fluent_shape_intersect_24_filled.png"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = True
SHOW_MIN_BUTTON = True
SHOW_CLOSE_BUTTON = True

CARD_STYLE_NORMAL = "SimpleCardWidget { background-color: rgba(255, 255, 255, 0.01); border: none; border-radius: 5px; }"
CARD_STYLE_HOVER = "SimpleCardWidget { background-color: rgba(255, 255, 255, 0.04); border: none; border-radius: 5px; }"
CARD_STYLE_SELECTED = "SimpleCardWidget { background-color: rgba(255, 255, 255, 0.1); border: none; border-radius: 5px; }"

DROP_AREA_STYLE_SHEET = """
    #DropAreaWidget {
        background-color: transparent;
        border: 2px dashed rgba(255, 255, 255, 0.1);
        border-radius: 5px;
    }
    #DropAreaWidget[isHovering="true"] {
        background-color: rgba(0, 255, 0, 0.06);
        border: 2px dashed rgba(0, 255, 0, 0.1);
    }
"""

BROWSE_BUTTON_STYLE = """
    QPushButton {
        background-color: transparent;
        border: none;
        padding: 5px;
        color: white;
    }
    QPushButton:hover {
        background-color: rgba(255, 255, 255, 0.04);
        border-radius: 5px;
    }
"""

DISABLED_TEXT_STYLE = "color: rgb(140, 140, 140);"
HOVER_TEXT_STYLE = "color: rgb(200, 255, 200);"

class ResourceItemDelegate(ListItemDelegate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uniform_badge_width = self._calculate_uniform_width(['LEGACY', 'CHUNK', 'EBX', 'RES'])

    def _calculate_uniform_width(self, all_types):
        font = QFont()
        font.setPixelSize(13)
        fm = QFontMetrics(font)
        max_width = 0
        for type_str in all_types:
            width = fm.horizontalAdvance(type_str)
            if width > max_width:
                max_width = width
        return max_width + 16

    def paint(self, painter: QPainter, option, index):
        super().paint(painter, option, index)
        painter.save()

        name = index.data(Qt.UserRole)
        type_str = index.data(Qt.UserRole + 1)
        legacy_name = index.data(Qt.UserRole + 2)

        text_to_display = legacy_name if type_str == 'LEGACY' and legacy_name else name

        font = painter.font()
        font.setPixelSize(13)
        painter.setFont(font)

        painter.setPen(option.palette.color(QPalette.ColorRole.Text))

        fm = QFontMetrics(font)
        badge_padding_v = 3
        badge_width = self.uniform_badge_width
        badge_height = fm.height() + 2 * badge_padding_v
        badge_y = option.rect.y() + (option.rect.height() - badge_height) // 2

        badge_rect = QRect(option.rect.left() + 8, badge_y, badge_width, badge_height)

        text_rect = option.rect.adjusted(badge_rect.right() + 8, 0, -8, 0)
        elided_text = fm.elidedText(str(text_to_display), Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_text)

        painter.setRenderHint(QPainter.Antialiasing)

        badge_color = QColor(128, 128, 128, 35)
        text_color = QColor(220, 220, 220) if isDarkTheme() else QColor(50, 50, 50)

        painter.setBrush(badge_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 4, 4)

        painter.setPen(text_color)
        painter.drawText(badge_rect, Qt.AlignCenter, type_str)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(200, 38)

class IconLoader(QObject):
    pixmapReady = Signal(object, QPixmap, str)

    def __init__(self):
        super().__init__()
        self.queue = deque()
        self.is_running = True

    def run(self):
        while self.is_running:
            if self.queue:
                card_obj, icon_data, icon_format, file_path = self.queue.popleft()
                pixmap = QPixmap()
                pixmap.loadFromData(icon_data, icon_format)
                if not pixmap.isNull():
                    self.pixmapReady.emit(card_obj, pixmap, file_path)
            else:
                QThread.msleep(50)

    def add_task(self, card_obj, icon_data, icon_format, file_path):
        self.queue.append((card_obj, icon_data, icon_format, file_path))

    def clear_queue(self):
        self.queue.clear()

class DataFetchWorker(QObject):
    finished = Signal(dict)

    def __init__(self, game_manager: GameManager, config_manager: ConfigManager, profile_name: Optional[str] = None, custom_file_paths: Optional[List[str]] = None):
        super().__init__()
        self.game_manager = game_manager
        self.config_manager = config_manager
        self.profile_name = profile_name
        self.custom_file_paths = custom_file_paths

    def run(self):
        try:
            data = self.game_manager.getModsCompatibilitInfo(self.config_manager, profile_name=self.profile_name, custom_file_paths=self.custom_file_paths)
            self.finished.emit(data or {})
        except Exception as e:
            ErrorHandler.handleError(f"Error fetching mods compatibility data: {e}")
            self.finished.emit({})

class ElidedLabel(BodyLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = text
        self._mode = Qt.ElideRight
        self.setText(text)

    def setText(self, text):
        self._full_text = text
        super().setText(text)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        fm = self.fontMetrics()
        elided_text = fm.elidedText(self._full_text, self._mode, self.width())
        painter.drawText(self.rect(), self.alignment(), elided_text)

class StatsCard(SimpleCardWidget):
    def __init__(self, label: str, value: str):
        super().__init__()
        self.setFixedSize(110, 60)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)
        self.value_label = BodyLabel(value)
        setFont(self.value_label, 16, QFont.Bold)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.text_label = CaptionLabel(label)
        self.text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)
        layout.addWidget(self.text_label)

    def setColor(self, color: QColor):
        self.setStyleSheet(f"background-color: {color.name()}; border-radius: 5px;")

    def setTextColor(self, color: QColor):
        style = f"color: {color.name()}; background-color: transparent;"
        self.value_label.setStyleSheet(style)
        self.text_label.setStyleSheet(style)

    def addDotBadge(self, success=True):
        dot = DotInfoBadge.success() if success else DotInfoBadge.error()
        dot.setFixedSize(10, 10)
        dot.setParent(self)

    def setDisabledLook(self, is_disabled: bool):
        normal_text_style = "color: white;"
        style = DISABLED_TEXT_STYLE if is_disabled else normal_text_style
        self.value_label.setStyleSheet(style)
        self.text_label.setStyleSheet(style)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for child in self.findChildren(DotInfoBadge):
            child.move(self.width() - child.width() - 8, 8)

class GameVersionCard(SimpleCardWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(220, 60)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)
        self.version_label = BodyLabel("-")
        setFont(self.version_label, 14, QFont.Bold)
        self.version_label.setAlignment(Qt.AlignCenter)
        self.title_label = CaptionLabel("Your Game TU")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.version_label)
        layout.addWidget(self.title_label)

    def setVersion(self, version_text: str):
        self.version_label.setText(version_text)

class ControlsPanel(SimpleCardWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(50)
        self.setStyleSheet(CARD_STYLE_NORMAL)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(10)

        self.profile_combo = ComboBox()
        self.profile_combo.setFixedWidth(160)
        self.profile_combo.setFixedHeight(28)

        self.filter_author = ComboBox()
        self.filter_author.setFixedWidth(160)
        self.filter_author.setFixedHeight(28)

        self.filter_enabled = ComboBox()
        self.filter_enabled.setFixedWidth(130)
        self.filter_enabled.setFixedHeight(28)

        self.filter_compat = ComboBox()
        self.filter_compat.setFixedWidth(130)
        self.filter_compat.setFixedHeight(28)

        layout.addWidget(BodyLabel("Profile:"))
        layout.addWidget(self.profile_combo)
        layout.addSpacing(15)
        layout.addWidget(BodyLabel("Author:"))
        layout.addWidget(self.filter_author)
        layout.addSpacing(15)
        layout.addWidget(BodyLabel("Status:"))
        layout.addWidget(self.filter_enabled)
        layout.addSpacing(15)
        layout.addWidget(BodyLabel("Compatibility:"))
        layout.addWidget(self.filter_compat)

class ModCard(SimpleCardWidget):
    modSelected = Signal(dict)

    def __init__(self, mod_info: dict, is_local_files_check=False):
        super().__init__()
        self.mod_info = mod_info
        self.icon_data = mod_info.get("icon_data")
        self.icon_format = mod_info.get("icon_format")
        self.is_selected = False
        self.is_hovered = False
        is_enabled = mod_info.get("is_enabled", False)
        compat_status = mod_info.get("compatibility_status")

        if not is_local_files_check:
            tooltip_id = "mod_enabled_dot" if is_enabled else "mod_disabled_dot"
            self.enabled_dot = DotInfoBadge.success() if is_enabled else DotInfoBadge.error()
            self.enabled_dot.setFixedSize(10, 10)
            self.dot_hover_area = QWidget(self)
            apply_tooltip(self.dot_hover_area, tooltip_id)
            self.enabled_dot.setParent(self)
        else:
            self.enabled_dot = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(50, 50)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setPixmap(FluentIcon.APPLICATION.icon().pixmap(40, 40))
        layout.addWidget(self.icon_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = ElidedLabel(mod_info.get("title", "Unknown Mod"))
        self.title_label.setMinimumWidth(400)
        self.title_label.setMaximumWidth(400)
        setFont(self.title_label, 13, QFont.Weight.Bold)

        author_label = CaptionLabel(f"By {mod_info.get('author', 'Unknown')}")
        tu_label = CaptionLabel(f"Requires TU: {mod_info.get('target_tu', 'Unknown')}")
        
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(author_label)
        info_layout.addWidget(tu_label)
        info_layout.addStretch()

        layout.addLayout(info_layout)
        layout.addStretch()

        self.compat_badge = None
        if compat_status == "COMPATIBLE":
            self.compat_badge = InfoBadge.success("Compatible")
        elif compat_status == "INCOMPATIBLE":
            self.compat_badge = InfoBadge.error("Incompatible")
        elif compat_status == "UNCERTAIN":
            self.compat_badge = InfoBadge.warning("Uncertain")

        if self.compat_badge:
            self.compat_badge.setParent(self)

        self.adjustSize()
        self._update_style()

    def sizeHint(self):
        return QSize(self.width(), self.title_label.sizeHint().height() + 55)

    def set_icon(self, pixmap: QPixmap):
        size = 52
        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), 0, 0)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        self.icon_label.setPixmap(rounded)

    def setSelected(self, selected: bool):
        self.is_selected = selected
        self._update_style()

    def _update_style(self):
        if self.is_selected:
            self.setStyleSheet(CARD_STYLE_SELECTED)
        elif self.is_hovered:
            self.setStyleSheet(CARD_STYLE_HOVER)
        else:
            self.setStyleSheet(CARD_STYLE_NORMAL)

    def enterEvent(self, event):
        self.is_hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self._update_style()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.modSelected.emit(self.mod_info)
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.enabled_dot:
            self.enabled_dot.move(self.width() - 25, 8)
            self.dot_hover_area.setGeometry(self.enabled_dot.geometry())
            self.dot_hover_area.raise_()
        if hasattr(self, 'compat_badge') and self.compat_badge:
            icon_x = self.icon_label.x()
            icon_width = self.icon_label.width()
            badge_width = self.compat_badge.width()
            new_x = icon_x + (icon_width - badge_width) // 2
            self.compat_badge.move(max(0, new_x), 0)
            self.compat_badge.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        self.setFixedHeight(self.sizeHint().height())

    def contextMenuEvent(self, event):
        menu = RoundMenu(parent=self)

        title = self.mod_info.get("title", "")
        author = self.mod_info.get('author', '')

        copy_title_action = QAction(FluentIcon.COPY.icon(), "Copy Mod Name")
        copy_title_action.triggered.connect(lambda: QApplication.clipboard().setText(title))

        copy_author_action = QAction(FluentIcon.COPY.icon(), "Copy Author Name")
        copy_author_action.triggered.connect(lambda: QApplication.clipboard().setText(author))

        menu.addAction(copy_title_action)
        menu.addAction(copy_author_action)

        menu.exec(event.globalPos())

class ModDetailsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_resources = []
        self.compatibility_status = "INCOMPATIBLE"

        all_types = ['EBX', 'RES', 'CHUNK', 'LEGACY']
        if 'LEGACY' in all_types:
            all_types.remove('LEGACY')
            self.all_resource_types = ['LEGACY'] + sorted(all_types)
        else:
            self.all_resource_types = sorted(all_types)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        self.card = SimpleCardWidget(self)
        self.card.setStyleSheet(CARD_STYLE_NORMAL)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(10)

        self.placeholder_initial = BodyLabel("Select a mod to see its affected assets.")
        self.placeholder_initial.setAlignment(Qt.AlignCenter)

        self.placeholder_no_files = BodyLabel(f"This mod does not affect any of the following assets types:\n"
                                              f"{', '.join(self.all_resource_types)}")
        self.placeholder_no_files.setAlignment(Qt.AlignCenter)

        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(8)
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0,0,0,0)
        self.title_label = BodyLabel("Affected Assets")
        setFont(self.title_label, 14, QFont.Weight.Bold)
        self.filter_combo = ComboBox()
        self.filter_combo.setFixedWidth(130)
        self.filter_combo.setFixedHeight(28)
        self.filter_combo.addItems(["All Types"] + self.all_resource_types)
        self.filter_combo.currentTextChanged.connect(self._populate_list)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.filter_combo)
        separator = QFrame()
        separator.setStyleSheet(SEPARATOR_STYLE)
        separator.setFixedHeight(1)

        self.resources_list = ListWidget()
        self.resources_list.setItemDelegate(ResourceItemDelegate(self.resources_list))
        self.resources_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.resources_list.customContextMenuRequested.connect(self._show_context_menu)

        self.resources_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.resources_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.list_scroll_area = ScrollArea(self)
        self.list_scroll_area.setWidget(self.resources_list)
        self.list_scroll_area.setWidgetResizable(False)
        self.list_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        details_layout.addLayout(title_layout)
        details_layout.addWidget(separator)
        details_layout.addWidget(self.list_scroll_area)
        card_layout.addWidget(self.placeholder_initial)
        card_layout.addWidget(self.placeholder_no_files)
        card_layout.addWidget(self.details_widget)
        main_layout.addWidget(self.card)

        self.placeholder_no_files.hide()
        self.details_widget.hide()

    def _show_context_menu(self, pos):
        item = self.resources_list.itemAt(pos)
        if not item: return

        name = item.data(Qt.UserRole)
        type_str = item.data(Qt.UserRole + 1)
        legacy_name = item.data(Qt.UserRole + 2)
        text_to_copy = legacy_name if type_str == 'LEGACY' and legacy_name else name

        menu = RoundMenu(parent=self)
        copy_action = QAction(FluentIcon.COPY.icon(), "Copy File Name")
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(text_to_copy))
        menu.addAction(copy_action)
        menu.exec(self.resources_list.mapToGlobal(pos))

    def update_details(self, mod_info: Optional[Dict]):
        if not mod_info:
            self.placeholder_initial.show()
            self.placeholder_no_files.hide()
            self.details_widget.hide()
            self.all_resources = []
            return

        self.compatibility_status = mod_info.get("compatibility_status", "INCOMPATIBLE")
        resources = mod_info.get('resources', [])

        filtered_resources = [
            r for r in resources if r.get('type') != 'EMBEDDED' and
            (r.get('legacy_chunk_name') or r.get('name', '')).lower().replace('\\', '/')
        ]

        def sort_key(r):
            res_type = r.get('type', '')
            is_legacy = 0 if res_type == 'LEGACY' else 1
            name = (r.get('legacy_chunk_name') or r.get('name', '')).lower()
            return (is_legacy, res_type, name)

        self.all_resources = sorted(filtered_resources, key=sort_key)

        if not self.all_resources:
            self.placeholder_initial.hide()
            self.placeholder_no_files.show()
            self.details_widget.hide()
        else:
            self.placeholder_initial.hide()
            self.placeholder_no_files.hide()
            self.details_widget.show()

        self._populate_list()

    def _populate_list(self):
        self.resources_list.clear()
        current_filter = self.filter_combo.currentText()

        if not self.all_resources:
            self.resources_list.setFixedSize(0, 0)
            return

        max_width = 0
        row_height = 38
        font = QFont(); font.setPixelSize(13); fm = QFontMetrics(font)
        visible_item_count = 0

        for res in self.all_resources:
            if current_filter == "All Types" or res.get('type') == current_filter:
                visible_item_count += 1
                list_item = QListWidgetItem()
                list_item.setSizeHint(QSize(200, row_height))
                list_item.setData(Qt.UserRole, res.get('name', 'N/A'))
                list_item.setData(Qt.UserRole + 1, res.get('type', 'N/A'))
                list_item.setData(Qt.UserRole + 2, res.get('legacy_chunk_name'))

                type_str = res.get('type')
                if type_str == 'LEGACY':
                    if self.compatibility_status == "COMPATIBLE":
                        bg_color = QColor(0, 255, 0, 15)
                    else:
                        bg_color = QColor(255, 0, 0, 15)
                    list_item.setBackground(bg_color)

                self.resources_list.addItem(list_item)

                name = res.get('legacy_chunk_name') if type_str == 'LEGACY' and res.get('legacy_chunk_name') else res.get('name')
                badge_width = self.resources_list.itemDelegate().uniform_badge_width
                name_width = fm.horizontalAdvance(str(name))
                item_width = badge_width + name_width + 40
                if item_width > max_width:
                    max_width = item_width

        total_height = visible_item_count * row_height

        container_width = self.list_scroll_area.viewport().width()
        final_width = max(max_width, container_width)

        self.resources_list.setFixedSize(final_width, total_height)

class ButtonManager(QObject):
    customCheckModeChanged = Signal(bool)

    def __init__(self, config_manager: ConfigManager, game_manager: GameManager, main_window):
        super().__init__()
        self.config_manager = config_manager
        self.game_manager = game_manager
        self.main_window = main_window
        self.btn_container = None
        self.buttons: Dict[str, QPushButton] = {}
        self.selected_mod_info: Optional[Dict] = None

    def create_buttons(self):
        toggle_container = QWidget()
        toggle_container.setMaximumWidth(150)
        toggle_layout = QHBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(0,0,0,0)
        toggle_layout.setSpacing(5)

        self.local_files_toggle = CheckBox("Custom Check")
        self.local_files_toggle.setStyleSheet("background: transparent; color: white;")
        self.local_files_toggle.toggled.connect(self._on_local_files_mode_changed)

        toggle_layout.addWidget(self.local_files_toggle, 0, Qt.AlignVCenter)

        button_configs = {
            "locate": (" Locate", FluentIcon.FOLDER, self.locate_mod, "locate_mod_button"),
            "search": (" Google it", FluentIcon.SEARCH, self.search_mod, "search_mod_button"),
        }
        for name, config in button_configs.items():
            btn = QPushButton(config[0])
            btn.setIcon(config[1].icon())
            btn.clicked.connect(config[2])
            apply_tooltip(btn, config[3])
            self.buttons[name] = btn
            btn.setEnabled(False)
        self._setup_button_layout(toggle_container)
        return self.btn_container

    def _setup_button_layout(self, toggle_widget):
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 0, 10, 0)
        btn_layout.setSpacing(5)
        btn_layout.addWidget(toggle_widget)
        btn_layout.addStretch()
        btn_layout.addWidget(self.buttons["locate"])
        btn_layout.addWidget(self.buttons["search"])
        self.btn_container = QWidget(objectName="ButtonContainer", fixedHeight=45)
        self.btn_container.setLayout(btn_layout)

    def update_button_state(self, mod_info: Optional[Dict]):
        self.selected_mod_info = mod_info
        is_mod_selected = mod_info is not None
        for btn in self.buttons.values():
            btn.setEnabled(is_mod_selected)

    def _select_file_in_explorer(self, path: str):
        if sys.platform == "win32":
            subprocess.run(['explorer', '/select,', os.path.normpath(path)], check=False)

    def locate_mod(self):
        if not self.selected_mod_info:
            return
        try:
            mod_path = self.selected_mod_info.get("file_path")
            if not mod_path or not os.path.exists(mod_path):
                ErrorHandler.handleError(f"Mod file not found at: {mod_path}")
                return

            self._select_file_in_explorer(mod_path)

        except Exception as e:
            ErrorHandler.handleError(f"Failed to locate mod: {e}")

    def search_mod(self):
        if not self.selected_mod_info:
            return
        title = self.selected_mod_info.get("title", "")
        author = self.selected_mod_info.get("author", "")
        query = f'"{title}" "{author}"'
        encoded_query = quote_plus(query)
        url = f"https://www.google.com/search?q={encoded_query}"
        webbrowser.open(url)

    def _on_local_files_mode_changed(self, is_checked):
        self.customCheckModeChanged.emit(is_checked)

class ModsCompatibilityInfo(BaseWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_manager = GameManager()
        self.config_manager = ConfigManager()
        self.mod_widgets: List[ModCard] = []
        self.selected_card: Optional[ModCard] = None
        self.data_thread: Optional[QThread] = None
        self.data_worker: Optional[QObject] = None
        self.icon_thread: Optional[QThread] = None
        self.icon_worker: Optional[IconLoader] = None
        self.button_manager: Optional[ButtonManager] = None
        self.bottom_bar_widget: Optional[QWidget] = None
        self.is_local_files_mode = False
        self.last_fetched_data = None
        self.custom_placeholder_widgets = []
        self.custom_file_paths = []

        self.pixmap_cache: Dict[str, QPixmap] = {}
        self._mod_populator_timer = QTimer(self)
        self._mod_populator_timer.setInterval(16)
        self._mod_populator_timer.timeout.connect(self._process_mod_batch)
        self._mod_generator = None

        self._initialize_window()
        self._start_icon_loader()

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _start_icon_loader(self):
        self.icon_thread = QThread()
        self.icon_worker = IconLoader()
        self.icon_worker.moveToThread(self.icon_thread)
        self.icon_thread.started.connect(self.icon_worker.run)
        self.icon_worker.pixmapReady.connect(self._on_pixmap_ready)
        self.icon_thread.start()

    def _on_pixmap_ready(self, card_obj: ModCard, pixmap: QPixmap, file_path: str):
        if card_obj in self.mod_widgets:
            card_obj.set_icon(pixmap)
            self.pixmap_cache[file_path] = pixmap

    def _initialize_window(self):
        self.setWindowTitle(TITLE)
        self.resize(*WINDOW_SIZE)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        try:
            self._setup_ui()
            self.show_loading(True)
            QTimer.singleShot(100, self._start_fetching_data)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to initialize window: {e}")
            self._cleanup_threads()
            self.close()

    def _setup_ui(self):
        self._setup_title_bar()
        self.main_content_widget = QWidget()
        self.main_content_widget.setStyleSheet("QWidget { background: transparent; border: none; }")
        self.container_layout = QVBoxLayout(self.main_content_widget)
        self.container_layout.setContentsMargins(20, 15, 20, 20)
        self.container_layout.setSpacing(12)

        self.controls_panel = ControlsPanel()
        self.controls_panel.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        self.controls_panel.filter_author.currentTextChanged.connect(self._apply_filter)
        self.controls_panel.filter_enabled.addItems(["All", "Enabled", "Disabled"])
        self.controls_panel.filter_enabled.currentTextChanged.connect(self._apply_filter)
        self.controls_panel.filter_compat.addItems(["All", "Compatible", "Uncertain", "Incompatible"])
        self.controls_panel.filter_compat.currentTextChanged.connect(self._apply_filter)

        stats_layout = self._create_stats_layout()

        self.incompatibility_help_label = CaptionLabel(
            "Info: An incompatible mod doesn't necessarily mean that all the assets within it will not work. "
            "If the title update has affected any legacy assets those legacy assets will not work at all. "
            "As for other assets types such as (EBX, RES, CHUNK) it is most likely that they will still work unless major changes have been made to it."
        )
        self.incompatibility_help_label.setWordWrap(True)
        self.incompatibility_help_label.setAlignment(Qt.AlignCenter)

        main_content_layout = QHBoxLayout()
        main_content_layout.setSpacing(12)
        main_content_layout.setContentsMargins(0,0,0,0)

        self.mods_scroll_area = ScrollArea()
        self.mods_scroll_area.setWidgetResizable(True)
        self.mods_scroll_area.setAcceptDrops(False)
        self.mods_scroll_area.dragEnterEvent = self.dragEnterEvent
        self.mods_scroll_area.dragLeaveEvent = self.dragLeaveEvent
        self.mods_scroll_area.dropEvent = self.dropEvent

        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("DropAreaWidget")
        self.scroll_widget.setStyleSheet('QWidget#DropAreaWidget { border: none; background: transparent; }')
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(8, 0, 8, 8)
        self.scroll_layout.setSpacing(6)

        self.list_loading_widget = QWidget()
        loading_layout = QVBoxLayout(self.list_loading_widget)
        loading_layout.setAlignment(Qt.AlignCenter)
        loading_label = BodyLabel("Loading...")
        setFont(loading_label, 14)
        loading_layout.addWidget(loading_label)

        self.list_stack = QStackedWidget()
        self.list_stack.addWidget(self.mods_scroll_area)
        self.list_stack.addWidget(self.list_loading_widget)

        self.mods_scroll_area.setWidget(self.scroll_widget)

        v_separator = QFrame()
        v_separator.setFixedWidth(1)
        v_separator.setStyleSheet(SEPARATOR_STYLE)

        self.details_panel = ModDetailsPanel()
        main_content_layout.addWidget(self.list_stack)
        main_content_layout.addWidget(v_separator)
        main_content_layout.addWidget(self.details_panel)
        main_content_layout.setStretchFactor(self.list_stack, 5)
        main_content_layout.setStretchFactor(self.details_panel, 4)

        separator = QFrame()
        separator.setStyleSheet(SEPARATOR_STYLE)
        separator.setFixedHeight(1)

        self.button_manager = ButtonManager(self.config_manager, self.game_manager, self)
        self.button_manager.customCheckModeChanged.connect(self._toggle_local_files_mode)
        buttons_widget = self.button_manager.create_buttons()

        separator2 = QFrame()
        separator2.setStyleSheet(SEPARATOR_STYLE)
        separator2.setFixedHeight(1)

        self.bottom_bar_widget = QWidget()
        bottom_layout = QVBoxLayout(self.bottom_bar_widget)
        bottom_layout.setContentsMargins(0,0,0,0)
        bottom_layout.setSpacing(0)
        bottom_layout.addWidget(separator2)
        bottom_layout.addWidget(buttons_widget)

        self.container_layout.addWidget(self.controls_panel)
        self.container_layout.addLayout(stats_layout)
        self.container_layout.addWidget(self.incompatibility_help_label)
        self.container_layout.addWidget(separator)
        self.container_layout.addLayout(main_content_layout)

        self.loading_widget = QWidget(self)
        loading_page_layout = QVBoxLayout(self.loading_widget)
        full_page_spinner = LoadingSpinner(self.loading_widget)
        full_page_loading_label = BodyLabel("Loading...")
        setFont(full_page_loading_label, 16)
        loading_page_layout.addStretch()
        loading_page_layout.addWidget(full_page_spinner, alignment=Qt.AlignCenter)
        loading_page_layout.addWidget(full_page_loading_label, alignment=Qt.AlignCenter)
        loading_page_layout.addStretch()

        self.main_stack = QStackedWidget()
        self.main_stack.addWidget(self.main_content_widget)
        self.main_stack.addWidget(self.loading_widget)

        self.main_layout.addWidget(self.main_stack)
        self.main_layout.addWidget(self.bottom_bar_widget)
        self.bottom_bar_widget.hide()

    def _create_stats_layout(self) -> QHBoxLayout:
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(10)
        self.game_version_card = GameVersionCard()
        v_separator = QFrame()
        v_separator.setFixedWidth(1)
        v_separator.setStyleSheet(SEPARATOR_STYLE)
        self.total_card = StatsCard("Total", "0")
        self.enabled_card = StatsCard("Enabled", "0")
        self.disabled_card = StatsCard("Disabled", "0")
        self.compatible_card = StatsCard("Compatible", "0")
        self.uncertain_card = StatsCard("Uncertain", "0")
        self.incompatible_card = StatsCard("Incompatible", "0")

        apply_tooltip(self.total_card, "stats_total_mods")
        apply_tooltip(self.enabled_card, "stats_enabled_mods")
        apply_tooltip(self.disabled_card, "stats_disabled_mods")
        apply_tooltip(self.compatible_card, "stats_compatible_mods")
        apply_tooltip(self.uncertain_card, "stats_uncertain_mods")
        apply_tooltip(self.incompatible_card, "stats_incompatible_mods")

        self.enabled_card.addDotBadge(success=True)
        self.disabled_card.addDotBadge(success=False)
        self.compatible_card.setColor(QColor(108, 203, 95))
        self.compatible_card.setTextColor(QColor("black"))
        self.uncertain_card.setColor(QColor(255, 244, 206))
        self.uncertain_card.setTextColor(QColor("black"))
        self.incompatible_card.setColor(QColor(255, 153, 164))
        self.incompatible_card.setTextColor(QColor("black"))

        stats_layout.addWidget(self.game_version_card)
        stats_layout.addWidget(v_separator)
        stats_layout.addWidget(self.total_card)
        stats_layout.addWidget(self.enabled_card)
        stats_layout.addWidget(self.disabled_card)
        stats_layout.addWidget(self.compatible_card)
        stats_layout.addWidget(self.uncertain_card)
        stats_layout.addWidget(self.incompatible_card)
        stats_layout.addStretch()
        return stats_layout

    def _setup_title_bar(self):
        title_bar = TitleBar(window=self, title=TITLE, icon_path=ICON_PATH, spacer_width=SPACER_WIDTH,
                             show_max_button=SHOW_MAX_BUTTON, show_min_button=SHOW_MIN_BUTTON,
                             show_close_button=SHOW_CLOSE_BUTTON, bar_height=BAR_HEIGHT)
        title_bar.create_title_bar()

    def _on_mod_selected(self, mod_info: dict):
        sender_card = self.sender()
        if self.selected_card and self.selected_card in self.mod_widgets:
            self.selected_card.setSelected(False)
        self.selected_card = sender_card
        self.selected_card.setSelected(True)
        self.details_panel.update_details(mod_info)
        if self.button_manager:
            self.button_manager.update_button_state(mod_info)

    def show_loading(self, show: bool):
        if show:
            self.main_stack.setCurrentWidget(self.loading_widget)
            self.bottom_bar_widget.hide()
            self.loading_widget.findChild(LoadingSpinner).start()
        else:
            self.main_stack.setCurrentWidget(self.main_content_widget)
            self.bottom_bar_widget.show()
            self.loading_widget.findChild(LoadingSpinner).stop()

    def _show_list_loading(self, show: bool):
        if show:
            self.list_stack.setCurrentWidget(self.list_loading_widget)
        else:
            self.list_stack.setCurrentWidget(self.mods_scroll_area)

    def _start_fetching_data(self, profile_name: Optional[str] = None, custom_file_paths: Optional[List[str]] = None):
        if self.data_thread and self.data_thread.isRunning():
            return
        if self.icon_worker: self.icon_worker.clear_queue()

        self.data_thread = QThread()
        self.data_worker = DataFetchWorker(self.game_manager, self.config_manager, profile_name, custom_file_paths)
        self.data_worker.moveToThread(self.data_thread)

        self.data_thread.started.connect(self.data_worker.run)
        self.data_worker.finished.connect(self._on_data_fetched)
        self.data_worker.finished.connect(self.data_thread.quit)
        self.data_worker.finished.connect(self.data_worker.deleteLater)
        self.data_thread.finished.connect(lambda: setattr(self, 'data_thread', None))
        self.data_thread.finished.connect(self.data_thread.deleteLater)

        self.data_thread.start()

    def _on_data_fetched(self, result: Dict):
        if not self.isVisible() or not result:
            self.show_loading(False)
            return

        self.details_panel.update_details(None)
        if self.button_manager:
            self.button_manager.update_button_state(None)

        if not self.is_local_files_mode:
            self.last_fetched_data = result

        current_profile = result.get("current_profile", "-")
        current_game_tu = result.get("current_game_tu", "-")
        mods = result.get("mods", [])

        authors = sorted(list(set(mod.get('author', 'Unknown') for mod in mods)))
        self.controls_panel.filter_author.blockSignals(True)
        self.controls_panel.filter_author.clear()
        self.controls_panel.filter_author.addItems(["All Authors"] + authors)
        self.controls_panel.filter_author.blockSignals(False)

        if not self.is_local_files_mode:
            self.controls_panel.profile_combo.blockSignals(True)
            self.controls_panel.profile_combo.clear()
            self.controls_panel.profile_combo.addItems(result.get("profiles", []))
            self.controls_panel.profile_combo.setCurrentText(current_profile)
            self.controls_panel.profile_combo.blockSignals(False)
        else:
            self.controls_panel.filter_author.setDisabled(not mods)
            self.controls_panel.filter_compat.setDisabled(not mods)

        enabled_count = sum(1 for mod in mods if mod.get("is_enabled", False))
        compatible_count = sum(1 for mod in mods if mod.get("compatibility_status") == "COMPATIBLE")
        uncertain_count = sum(1 for mod in mods if mod.get("compatibility_status") == "UNCERTAIN")
        incompatible_count = sum(1 for mod in mods if mod.get("compatibility_status") == "INCOMPATIBLE")

        self.game_version_card.setVersion(current_game_tu)
        self.total_card.value_label.setText(str(len(mods)))
        self.compatible_card.value_label.setText(str(compatible_count))
        self.uncertain_card.value_label.setText(str(uncertain_count))
        self.incompatible_card.value_label.setText(str(incompatible_count))

        if self.is_local_files_mode:
            self.enabled_card.value_label.setText("-")
            self.disabled_card.value_label.setText("-")
        else:
            self.enabled_card.value_label.setText(str(enabled_count))
            self.disabled_card.value_label.setText(str(len(mods) - enabled_count))

        self._populate_mods_list(mods)

    def _clear_scroll_layout(self):
        self._mod_populator_timer.stop()
        self._mod_generator = None
        self.selected_card = None
        self.custom_placeholder_widgets.clear()

        if self.scroll_widget:
            self.scroll_widget.setUpdatesEnabled(False)

        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.mod_widgets.clear()

        if self.scroll_widget:
            self.scroll_widget.setUpdatesEnabled(True)

    def _populate_mods_list(self, mods: List[Dict]):
        self._clear_scroll_layout()

        if not mods:
            if self.is_local_files_mode:
                self._setup_local_files_mode_placeholder()
            else:
                no_mods_label = BodyLabel("No mods found in this profile.")
                no_mods_label.setAlignment(Qt.AlignCenter)
                self.scroll_layout.addWidget(no_mods_label)
            self._show_list_loading(False)
            self.show_loading(False)
            return

        self._mod_generator = (mod for mod in sorted(mods, key=lambda x: x.get('title', '')))
        self._mod_populator_timer.start()

    def _process_mod_batch(self):
        if self.scroll_widget:
            self.scroll_widget.setUpdatesEnabled(False)

        for _ in range(30):
            try:
                mod_info = next(self._mod_generator)
                card = ModCard(mod_info, is_local_files_check=self.is_local_files_mode)
                card.setProperty("is_enabled", mod_info.get("is_enabled", False))
                card.setProperty("compatibility_status", mod_info.get("compatibility_status"))
                card.modSelected.connect(self._on_mod_selected)
                self.mod_widgets.append(card)
                self.scroll_layout.addWidget(card)

                file_path = mod_info.get("file_path")
                if file_path in self.pixmap_cache:
                    card.set_icon(self.pixmap_cache[file_path])
                elif card.icon_data and self.icon_worker:
                    self.icon_worker.add_task(card, card.icon_data, card.icon_format, file_path)

            except StopIteration:
                self._mod_populator_timer.stop()
                self.scroll_layout.addStretch()
                self._apply_filter()
                self._show_list_loading(False)
                self.show_loading(False)
                break

        if self.scroll_widget:
            self.scroll_widget.setUpdatesEnabled(True)

    def _apply_filter(self):
        author_filter = self.controls_panel.filter_author.currentText()
        compat_filter = self.controls_panel.filter_compat.currentText()
        enabled_filter = self.controls_panel.filter_enabled.currentText()

        if self.scroll_widget:
            self.scroll_widget.setUpdatesEnabled(False)

        for card in self.mod_widgets:
            show = True
            compat_status = card.property("compatibility_status")
            author = card.mod_info.get('author', 'Unknown')

            if author_filter != "All Authors" and author != author_filter:
                show = False

            if show and compat_filter == "Compatible" and compat_status != "COMPATIBLE":
                show = False
            elif show and compat_filter == "Uncertain" and compat_status != "UNCERTAIN":
                show = False
            elif show and compat_filter == "Incompatible" and compat_status != "INCOMPATIBLE":
                show = False

            if not self.is_local_files_mode:
                is_enabled = card.property("is_enabled")
                if show and enabled_filter == "Enabled" and not is_enabled:
                    show = False
                elif show and enabled_filter == "Disabled" and is_enabled:
                    show = False

            card.setVisible(show)

        if self.scroll_widget:
            self.scroll_widget.setUpdatesEnabled(True)

    def _on_profile_changed(self, profile_name: str):
        if self.controls_panel.profile_combo.signalsBlocked(): return
        self._show_list_loading(True)
        self._start_fetching_data(profile_name=profile_name)

    def _setup_local_files_mode_placeholder(self):
        placeholder = QWidget()
        self.custom_placeholder_widgets = []
        layout = QVBoxLayout(placeholder)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)

        drop_label = BodyLabel("Drop .fifamod files here or")
        drop_label.setAlignment(Qt.AlignCenter)

        browse_button = QPushButton(" Browse Files...")
        browse_button.setIcon(FluentIcon.DOCUMENT.icon())
        browse_button.setFixedHeight(32)
        browse_button.setStyleSheet(BROWSE_BUTTON_STYLE)
        browse_button.clicked.connect(self._browse_for_mods)

        self.custom_placeholder_widgets.extend([drop_label, browse_button])

        h_layout = QHBoxLayout()
        h_layout.setSpacing(5)
        h_layout.setAlignment(Qt.AlignCenter)
        h_layout.addWidget(drop_label)
        h_layout.addWidget(browse_button)

        layout.addStretch()
        layout.addLayout(h_layout)
        layout.addStretch()

        self.scroll_layout.addWidget(placeholder)

    def _toggle_local_files_mode(self, is_checked: bool):
        self.is_local_files_mode = is_checked
        self.mods_scroll_area.setAcceptDrops(is_checked)
        self.custom_file_paths.clear()

        self.controls_panel.profile_combo.setDisabled(is_checked)
        self.controls_panel.filter_enabled.setDisabled(is_checked)

        self.enabled_card.setDisabledLook(is_checked)
        self.disabled_card.setDisabledLook(is_checked)

        self._clear_scroll_layout()
        if is_checked:
            self.scroll_widget.setStyleSheet(DROP_AREA_STYLE_SHEET)
            self.scroll_layout.setContentsMargins(8, 8, 8, 8)
            self._setup_local_files_mode_placeholder()
            self.controls_panel.filter_author.clear()
            self.controls_panel.filter_author.addItem("All Authors")
            self.controls_panel.filter_author.setDisabled(True)
            self.controls_panel.filter_compat.setDisabled(True)
            self.total_card.value_label.setText("0")
            self.enabled_card.value_label.setText("-")
            self.disabled_card.value_label.setText("-")
            self.compatible_card.value_label.setText("0")
            self.uncertain_card.value_label.setText("0")
            self.incompatible_card.value_label.setText("0")
        else:
            self.scroll_widget.setStyleSheet('QWidget#DropAreaWidget { border: none; background: transparent; }')
            self.scroll_layout.setContentsMargins(8, 0, 8, 8)
            self.controls_panel.filter_author.setDisabled(False)
            self.controls_panel.filter_compat.setDisabled(False)
            self._show_list_loading(True)
            if self.last_fetched_data:
                self._on_data_fetched(self.last_fetched_data)
            else:
                self._start_fetching_data()

    def _browse_for_mods(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select mod files", "", "FIFA Mod Files (*.fifamod)")
        if files:
            new_files = [f for f in files if f not in self.custom_file_paths]
            self.custom_file_paths.extend(new_files)
            if self.custom_file_paths:
                self._show_list_loading(True)
                self._start_fetching_data(custom_file_paths=self.custom_file_paths)

    def dragEnterEvent(self, event):
        if self.is_local_files_mode and event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().endswith('.fifamod') for url in urls):
                self.scroll_widget.setProperty("isHovering", True)
                self.scroll_widget.style().polish(self.scroll_widget)
                for widget in self.custom_placeholder_widgets:
                    widget.setStyleSheet(HOVER_TEXT_STYLE)
                event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        if self.is_local_files_mode:
            self.scroll_widget.setProperty("isHovering", False)
            self.scroll_widget.style().polish(self.scroll_widget)
            for widget in self.custom_placeholder_widgets:
                widget.setStyleSheet("")
        event.accept()

    def dropEvent(self, event):
        if self.is_local_files_mode:
            self.scroll_widget.setProperty("isHovering", False)
            self.scroll_widget.style().polish(self.scroll_widget)
            for widget in self.custom_placeholder_widgets:
                widget.setStyleSheet("")
            if event.mimeData().hasUrls():
                files = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile().endswith('.fifamod')]
                if files:
                    new_files = [f for f in files if f not in self.custom_file_paths]
                    self.custom_file_paths.extend(new_files)
                    if self.custom_file_paths:
                        self._show_list_loading(True)
                        self._start_fetching_data(custom_file_paths=self.custom_file_paths)
                    event.acceptProposedAction()

    def closeEvent(self, event):
        self._cleanup_threads()
        super().closeEvent(event)

    def _cleanup_threads(self):
        if self.icon_worker: self.icon_worker.is_running = False
        if self.icon_thread: self.icon_thread.quit(); self.icon_thread.wait()
        if self.data_thread and self.data_thread.isRunning(): self.data_thread.quit(); self.data_thread.wait()

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = ModsCompatibilityInfo()
    window.center_window()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()