import sys
import os
import re
import subprocess
from typing import Optional, Dict
from collections import Counter
from functools import cmp_to_key

from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QSize, QRect
from PySide6.QtGui import (QFont, QColor, QFontMetrics, QPainter, QAction,
                           QGuiApplication, QPalette)
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QWidget, QHBoxLayout, QFrame,
                               QPushButton, QStackedWidget, QListWidgetItem)

from qfluentwidgets import (ComboBox, ListWidget, ListItemDelegate, SimpleCardWidget, FluentIcon, Theme, setTheme,
                            setThemeColor, BodyLabel, CaptionLabel, setFont, isDarkTheme,
                            RoundMenu, SearchLineEdit)

from UIComponents.Personalization import BaseWindow
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.Spinner import LoadingSpinner
from Core.GameManager import GameManager
from Core.ErrorHandler import ErrorHandler
from Core.Logger import logger
from Libraries.SteamDDLib.app.manifest_parser import Manifest

TITLE = "Files Changelog:"
WINDOW_SIZE = (990, 640)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/ic_fluent_history_24_filled.png"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.08);"
CARD_STYLE_NORMAL = "SimpleCardWidget { background-color: rgba(255, 255, 255, 0.01); border: 1px solid transparent; border-radius: 5px; }"
CARD_STYLE_HOVER = "SimpleCardWidget { background-color: rgba(255, 255, 255, 0.04); border: 1px solid transparent; border-radius: 5px; }"
CARD_STYLE_SELECTED = "SimpleCardWidget { background-color: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 5px; }"

class DataFetchWorker(QObject):
    finished = Signal(str, dict)

    def __init__(self, gm: GameManager, g_id: str, d_type: str, m_id: str):
        super().__init__()
        self.gm, self.g_id, self.d_type, self.m_id = gm, g_id, d_type, m_id

    def run(self):
        try:
            data = self.gm.fetchDepotChangelog(self.g_id, self.d_type, self.m_id) or {}
            self.finished.emit(self.d_type, data)
        except Exception as e:
            logger.error(f"Exception in DataFetchWorker for {self.d_type}: {e}", exc_info=True)
            self.finished.emit(self.d_type, {})

class ManifestFetchWorker(QObject):
    finished = Signal(str, object)

    def __init__(self, gm: GameManager, game_id: str, depot_type: str, depot_id: str, manifest_id: str):
        super().__init__()
        self.gm, self.game_id, self.depot_type, self.depot_id, self.manifest_id = gm, game_id, depot_type, depot_id, manifest_id

    def run(self):
        manifest = self.gm.fetchDepotManifest(self.game_id, self.depot_type, self.depot_id, self.manifest_id)
        self.finished.emit(self.depot_type, manifest)

class FileListItemDelegate(ListItemDelegate):
    def _format_bytes(self, size):
        if not isinstance(size, (int, float)) or size == 0:
            return ""
        prefix = "+" if size > 0 else "-"
        size = abs(size)
        power, n, labels = 1024, 0, {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size >= power and n < len(labels) - 1:
            size /= power
            n += 1
        return f"{prefix}{size:.2f} {labels[n]}".replace(".00", "")

    def paint(self, painter: QPainter, option, index):
        super().paint(painter, option, index)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        file_info = index.data(Qt.UserRole)
        status = file_info.get("status")

        if status == "Added":
            painter.setBrush(QColor(0, 255, 0, 10))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(option.rect, 5, 5)
        elif status == "Removed":
            painter.setBrush(QColor(255, 0, 0, 10))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(option.rect, 5, 5)
        elif status == "Modified":
            painter.setBrush(QColor(255, 193, 7, 10))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(option.rect, 5, 5)

        name = file_info.get("name", "N/A")
        type_str = os.path.splitext(name)[1].upper().replace('.', '')

        padding = 8
        badge_font = QFont()
        badge_font.setPixelSize(12)
        fm_badge = QFontMetrics(badge_font)

        type_badge_rect = QRect()
        if type_str:
            type_badge_width = fm_badge.horizontalAdvance(type_str) + 16
            type_badge_rect = QRect(option.rect.left() + padding, option.rect.center().y() - 11, type_badge_width, 22)
            painter.setBrush(QColor(128, 128, 128, 35))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(type_badge_rect, 4, 4)
            text_color = QColor(220, 220, 220) if isDarkTheme() else QColor(50, 50, 50)
            painter.setPen(text_color)
            painter.setFont(badge_font)
            painter.drawText(type_badge_rect, Qt.AlignCenter, type_str)

        fixed_badge_width = 85
        status_badge_rect = QRect(option.rect.right() - padding - fixed_badge_width, option.rect.center().y() - 11, fixed_badge_width, 22)

        if status == "Added":
            bg_color, text_color = QColor(108, 203, 95, 40), QColor(138, 233, 125)
        elif status == "Removed":
            bg_color, text_color = QColor(255, 153, 164, 40), QColor(255, 183, 194)
        elif status == "Modified":
            bg_color, text_color = QColor(255, 193, 7, 40), QColor(255, 224, 130)
        else:
            bg_color, text_color = QColor(128, 128, 128, 35), QColor(200, 200, 200)

        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(status_badge_rect, 4, 4)
        painter.setPen(text_color)
        painter.setFont(badge_font)
        painter.drawText(status_badge_rect, Qt.AlignCenter, status)

        size_diff = 0
        if status == "Modified":
            size_diff = int(file_info.get("changes", {}).get("size", {}).get("new", 0)) - int(file_info.get("changes", {}).get("size", {}).get("old", 0))
        elif status == "Added":
            size_diff = int(file_info.get("size", 0))
        elif status == "Removed":
            size_diff = -int(file_info.get("size", 0))

        size_text = self._format_bytes(size_diff)
        size_text_width = fm_badge.horizontalAdvance(size_text)

        name_font = QFont()
        name_font.setPixelSize(13)
        fm_name = QFontMetrics(name_font)

        left_bound = type_badge_rect.right() + padding if type_str else option.rect.left() + padding
        right_bound = status_badge_rect.left() - padding
        available_width = right_bound - left_bound - size_text_width - (padding if size_text else 0)

        elided_text = fm_name.elidedText(name, Qt.ElideMiddle, available_width)

        painter.setFont(name_font)
        painter.drawText(QRect(left_bound, option.rect.y(), available_width, option.rect.height()), Qt.AlignVCenter | Qt.AlignLeft, elided_text)

        if size_text:
            name_width = fm_name.horizontalAdvance(elided_text)
            size_x_pos = left_bound + name_width + padding
            size_rect = QRect(size_x_pos, option.rect.y(), size_text_width, option.rect.height())
            if size_diff > 0:
                painter.setPen(QColor("#6CCB5F"))
            elif size_diff < 0:
                painter.setPen(QColor("#FF99A4"))
            else:
                painter.setPen(QColor(200, 200, 200))
            painter.setFont(badge_font)
            painter.drawText(size_rect, Qt.AlignVCenter | Qt.AlignLeft, size_text)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(200, 42)

class StatsCard(SimpleCardWidget):
    clicked = Signal()

    def __init__(self, label: str):
        super().__init__()
        self.setFixedSize(110, 60)
        self.setStyleSheet(CARD_STYLE_NORMAL)
        self.is_hovered = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        self.value_label = BodyLabel("0")
        setFont(self.value_label, 16, QFont.Weight.Bold)
        self.value_label.setAlignment(Qt.AlignCenter)

        self.text_label = CaptionLabel(label)
        self.text_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.value_label)
        layout.addWidget(self.text_label)

    def setValue(self, value: str):
        self.value_label.setText(value)

    def enterEvent(self, event):
        self.is_hovered=True
        self.setStyleSheet(CARD_STYLE_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered=False
        self.setStyleSheet(CARD_STYLE_NORMAL)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.setStyleSheet(CARD_STYLE_SELECTED)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setStyleSheet(CARD_STYLE_HOVER if self.is_hovered else CARD_STYLE_NORMAL)
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

class ComplexStatsCard(SimpleCardWidget):
    clicked = Signal()

    def __init__(self, label: str):
        super().__init__()
        self.setFixedSize(130, 60)
        self.setStyleSheet(CARD_STYLE_NORMAL)
        self.is_hovered = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 2, 8, 2)
        main_layout.setSpacing(0)

        self.value_label = BodyLabel("0")
        setFont(self.value_label, 16, QFont.Weight.Bold)
        self.value_label.setAlignment(Qt.AlignCenter)

        self.text_label = CaptionLabel(label)
        self.text_label.setAlignment(Qt.AlignCenter)

        main_layout.addStretch(1)
        main_layout.addWidget(self.value_label)
        main_layout.addWidget(self.text_label)
        main_layout.addStretch(1)

        self.diff_label = CaptionLabel("±0", self)
        self.diff_label.setAlignment(Qt.AlignRight | Qt.AlignTop)

    def _update_diff_label_position(self):
        self.diff_label.move(self.width() - self.diff_label.width() - 8, 4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_diff_label_position()

    def _format_diff_count(self, count):
        if not isinstance(count, int) or count == 0:
            return "±0"
        return f"{count:+}"

    def setValues(self, diff: int, new_total: int):
        self.diff_label.setText(self._format_diff_count(diff))
        if diff == 0:
            self.diff_label.setStyleSheet("color: gray;")
        else:
            self.diff_label.setStyleSheet("color: #6CCB5F;" if diff > 0 else "color: #FF99A4;")

        self.diff_label.adjustSize()
        self._update_diff_label_position()
        self.value_label.setText(str(new_total))

    def enterEvent(self, event):
        self.is_hovered=True
        self.setStyleSheet(CARD_STYLE_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered=False
        self.setStyleSheet(CARD_STYLE_NORMAL)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.setStyleSheet(CARD_STYLE_SELECTED)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setStyleSheet(CARD_STYLE_HOVER if self.is_hovered else CARD_STYLE_NORMAL)
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

class DepotsSizeCard(SimpleCardWidget):
    def __init__(self, label: str):
        super().__init__()
        self.setFixedSize(220, 60)
        self.setStyleSheet(CARD_STYLE_NORMAL)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 2, 8, 2)
        main_layout.setSpacing(0)

        self.value_label = BodyLabel("0 B")
        setFont(self.value_label, 16, QFont.Weight.Bold)
        self.value_label.setAlignment(Qt.AlignCenter)

        self.text_label = CaptionLabel(label)
        self.text_label.setAlignment(Qt.AlignCenter)

        main_layout.addStretch(1)
        main_layout.addWidget(self.value_label)
        main_layout.addWidget(self.text_label)
        main_layout.addStretch(1)

        self.diff_label = CaptionLabel("±0 B", self)
        self.diff_label.setAlignment(Qt.AlignRight | Qt.AlignTop)

    def _update_diff_label_position(self):
        self.diff_label.move(self.width() - self.diff_label.width() - 8, 4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_diff_label_position()

    def _format_diff_bytes(self, size):
        if not isinstance(size, (int, float)) or size == 0:
            return "±0 B"
        prefix = "+" if size > 0 else "-"
        size = abs(size)
        power, n, labels = 1024, 0, {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size >= power and n < len(labels) - 1:
            size /= power
            n += 1
        return f"{prefix}{size:.2f} {labels[n]}".replace(".00", "")

    def _format_total_bytes(self, size):
        if not isinstance(size, (int, float)) or size == 0:
            return "0 B"
        power, n, labels = 1024, 0, {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size >= power and n < len(labels) - 1:
            size /= power
            n += 1
        return f"{size:.2f} {labels[n]}".replace(".00", "")

    def setValue(self, diff: int, new_total: int):
        self.diff_label.setText(self._format_diff_bytes(diff))
        if diff == 0:
            self.diff_label.setStyleSheet("color: gray;")
        else:
            self.diff_label.setStyleSheet("color: #6CCB5F;" if diff > 0 else "color: #FF99A4;")

        self.diff_label.adjustSize()
        self._update_diff_label_position()
        self.value_label.setText(self._format_total_bytes(new_total))

class DepotVersionCard(SimpleCardWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(220, 60)
        self.setStyleSheet(CARD_STYLE_NORMAL)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        self.version_label = BodyLabel("-")
        setFont(self.version_label, 14, QFont.Weight.Bold)
        self.version_label.setAlignment(Qt.AlignCenter)

        self.title_label = CaptionLabel("Manifest Creation Date")
        self.title_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.version_label)
        layout.addWidget(self.title_label)

    def setVersion(self, date_text: str):
        self.version_label.setText(date_text)

class FilesChangelogWindow(BaseWindow):
    def __init__(self, game_manager: GameManager, game_root_path: str, game_id: str,
                 main_depot_id: str, eng_us_depot_id: Optional[str],
                 main_manifest_id: str, eng_us_manifest_id: Optional[str],
                 update_name: str, parent=None):
        super().__init__(parent)
        self.game_manager = game_manager
        self.game_root_path = game_root_path
        self.game_id = game_id
        self.main_depot_id = main_depot_id
        self.eng_us_depot_id = eng_us_depot_id
        self.main_manifest_id = main_manifest_id
        self.eng_us_manifest_id = eng_us_manifest_id
        self.update_name = update_name
        self.threads = []

        self.main_changelog_data = None
        self.lang_changelog_data = None
        self.main_manifest_data = None
        self.lang_manifest_data = None
        self.fetches_completed = 0

        self.all_changelog_files = []
        self.all_depot_files = []
        self._initialize_window()

    def _initialize_window(self):
        self.setWindowTitle(TITLE)
        self.resize(*WINDOW_SIZE)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        try:
            self._setup_ui()
            self.show_loading(True)
            QTimer.singleShot(100, self._fetchAllDataInitially)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to initialize window: {e}")
            self.close()

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _setup_ui(self):
        TitleBar(window=self, title=f"{TITLE} {self.update_name}", icon_path=ICON_PATH).create_title_bar()
        self.main_content_widget = QWidget()
        self.main_content_widget.setStyleSheet("background: transparent; border: none;")

        container_layout = QVBoxLayout(self.main_content_widget)
        container_layout.setContentsMargins(20, 15, 20, 20)
        container_layout.setSpacing(12)

        self.controls_panel = self._create_controls_panel()
        stats_layout = self._create_stats_layout()
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("Search for files...")
        self.search_bar.textChanged.connect(self._populate_list)

        self.list_widget = ListWidget()
        self.list_widget.setItemDelegate(FileListItemDelegate(self.list_widget))
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.itemDoubleClicked.connect(self._locate_selected_file)
        self.list_widget.currentItemChanged.connect(self._update_locate_button_state)

        self.loading_widget = QWidget(self)
        loading_page_layout = QVBoxLayout(self.loading_widget)
        loading_page_layout.addStretch()
        loading_page_layout.addWidget(LoadingSpinner(self.loading_widget), alignment=Qt.AlignCenter)
        loading_page_label = BodyLabel("Fetching all depot data...")
        loading_page_label.setAlignment(Qt.AlignCenter)
        loading_page_layout.addWidget(loading_page_label)
        loading_page_layout.addStretch()

        self.main_stack = QStackedWidget()
        self.main_stack.addWidget(self.main_content_widget)
        self.main_stack.addWidget(self.loading_widget)
        self._setup_bottom_bar()

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(SEPARATOR_STYLE)

        container_layout.addWidget(self.controls_panel)
        container_layout.addLayout(stats_layout)
        container_layout.addWidget(separator)
        container_layout.addWidget(self.search_bar)
        container_layout.addWidget(self.list_widget)

        self.main_layout.addWidget(self.main_stack)
        self.main_layout.addWidget(self.bottom_bar_widget)
        self.main_content_widget.hide()

    def _create_controls_panel(self) -> QWidget:
        panel = SimpleCardWidget()
        panel.setStyleSheet(CARD_STYLE_NORMAL)
        panel.setFixedHeight(50)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(10)

        self.view_mode_combo = ComboBox()
        self.view_mode_combo.addItems(["Affected Files Only", "All Depot Files"])
        self.view_mode_combo.setFixedWidth(180)
        self.view_mode_combo.setFixedHeight(28)
        self.view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)

        self.filter_status_combo = ComboBox()
        self.filter_status_combo.addItems(["All Changes", "Added", "Removed", "Modified"])
        self.filter_status_combo.setFixedWidth(140)
        self.filter_status_combo.setFixedHeight(28)
        self.filter_status_combo.currentTextChanged.connect(self._populate_list)

        self.filter_type_combo = ComboBox()
        self.filter_type_combo.setFixedWidth(140)
        self.filter_type_combo.setFixedHeight(28)
        self.filter_type_combo.currentTextChanged.connect(self._populate_list)

        self.depot_combo = ComboBox()

        depot_items = ["All Depots", "Main"]
        if self.eng_us_manifest_id:
            depot_items.append("Language (eng_us)")

        self.depot_combo.addItems(depot_items)

        self.depot_combo.setFixedWidth(140)
        self.depot_combo.setFixedHeight(28)
        self.depot_combo.currentIndexChanged.connect(self._populate_list)

        layout.addWidget(BodyLabel("View:"))
        layout.addWidget(self.view_mode_combo)
        layout.addSpacing(15)
        layout.addWidget(BodyLabel("Status:"))
        layout.addWidget(self.filter_status_combo)
        layout.addSpacing(15)
        layout.addWidget(BodyLabel("File Type:"))
        layout.addWidget(self.filter_type_combo)
        layout.addSpacing(15)
        layout.addWidget(BodyLabel("Depot:"))
        layout.addWidget(self.depot_combo)
        layout.addStretch()

        return panel

    def _create_stats_layout(self):
        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.version_card = DepotVersionCard()
        self.size_diff_card = DepotsSizeCard("Depots Size")

        v_separator = QFrame()
        v_separator.setFixedWidth(1)
        v_separator.setStyleSheet(SEPARATOR_STYLE)

        self.total_card = ComplexStatsCard("Depot Files")
        self.added_card = StatsCard("Added")
        self.removed_card = StatsCard("Removed")
        self.modified_card = StatsCard("Modified")

        self.total_card.clicked.connect(lambda: self.view_mode_combo.setCurrentIndex(1))
        self.added_card.clicked.connect(lambda: (self.filter_status_combo.setCurrentText("Added"), self.view_mode_combo.setCurrentIndex(0)))
        self.removed_card.clicked.connect(lambda: (self.filter_status_combo.setCurrentText("Removed"), self.view_mode_combo.setCurrentIndex(0)))
        self.modified_card.clicked.connect(lambda: (self.filter_status_combo.setCurrentText("Modified"), self.view_mode_combo.setCurrentIndex(0)))

        layout.addWidget(self.version_card)
        layout.addWidget(self.size_diff_card)
        layout.addWidget(v_separator)
        layout.addWidget(self.total_card)
        layout.addWidget(self.added_card)
        layout.addWidget(self.removed_card)
        layout.addWidget(self.modified_card)
        layout.addStretch()

        return layout

    def _setup_bottom_bar(self):
        self.bottom_bar_widget = QWidget()
        self.bottom_bar_widget.setObjectName("ButtonContainer")
        self.bottom_bar_widget.setFixedHeight(46)

        bottom_main_layout = QVBoxLayout(self.bottom_bar_widget)
        bottom_main_layout.setContentsMargins(0,0,0,0)
        bottom_main_layout.setSpacing(0)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(SEPARATOR_STYLE)

        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(10,0,10,0)

        self.locate_button = QPushButton(" Locate")
        self.locate_button.setIcon(FluentIcon.FOLDER.icon())
        self.locate_button.clicked.connect(self._locate_selected_file)
        self.locate_button.setEnabled(False)

        btn_layout.addStretch()
        btn_layout.addWidget(self.locate_button)

        bottom_main_layout.addWidget(separator)
        bottom_main_layout.addWidget(btn_container)
        self.bottom_bar_widget.hide()

    def show_loading(self, show: bool):
        if show:
            self.main_stack.setCurrentWidget(self.loading_widget)
            self.main_content_widget.hide()
            self.bottom_bar_widget.hide()
            self.loading_widget.findChild(LoadingSpinner).start()
        else:
            self.main_stack.setCurrentWidget(self.main_content_widget)
            self.main_content_widget.show()
            self.bottom_bar_widget.show()
            self.loading_widget.findChild(LoadingSpinner).stop()

    def _fetchAllDataInitially(self):
        thread = QThread()
        worker = ManifestFetchWorker(self.game_manager, self.game_id, "Main", self.main_depot_id, self.main_manifest_id)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_main_manifest_fetched)
        thread.start()
        self.threads.append((thread, worker))

    def _on_main_manifest_fetched(self, depot_type, manifest_data):
        if not manifest_data:
            ErrorHandler.handleError("This update has no depot manifest data available.")
            self.close()
            return

        self.main_manifest_data = manifest_data
        self.fetches_completed = 1
        
        self._fetch_remaining_data()
        
    def _fetch_remaining_data(self):
        tasks = [("changelog", "Main", self.main_manifest_id, self.main_depot_id)]
        if self.eng_us_manifest_id and self.eng_us_depot_id:
            tasks.extend([("changelog", "Language", self.eng_us_manifest_id, self.eng_us_depot_id),
                          ("manifest", "Language", self.eng_us_manifest_id, self.eng_us_depot_id)])

        self.fetches_to_complete = 1 + len(tasks)
        
        for fetch_type, depot_type_str, manifest_id, depot_id in tasks:
            thread = QThread()
            worker = None
            if fetch_type == "changelog":
                worker = DataFetchWorker(self.game_manager, self.game_id, depot_type_str, manifest_id)
            else:
                worker = ManifestFetchWorker(self.game_manager, self.game_id, depot_type_str, depot_id, manifest_id)
            
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(self._on_fetch_complete)
            thread.start()
            self.threads.append((thread, worker))

    def _on_fetch_complete(self, depot_type, data):
        if isinstance(data, dict):
            if depot_type == "Main":
                self.main_changelog_data = data
            else:
                self.lang_changelog_data = data
        elif isinstance(data, Manifest):
            if depot_type == "Main":
                self.main_manifest_data = data
            else:
                self.lang_manifest_data = data

        self.fetches_completed += 1
        if self.fetches_completed >= self.fetches_to_complete:
            self._processAllFetchedData()

    def _processAllFetchedData(self):
        changelog_data = self._merge_depot_data(self.main_changelog_data, self.lang_changelog_data)
        manifest_data = self._merge_manifest_data(self.main_manifest_data, self.lang_manifest_data)

        changelog_files_map = {f["name"]: f for status, key in [("Modified", "modified"), ("Added", "added"), ("Removed", "deleted")] for f in changelog_data.get(key, []) for f in [dict(f, status=status)]}
        self.all_changelog_files = list(changelog_files_map.values())

        if manifest_data:
            self.all_depot_files = [changelog_files_map.get(f.name, {"name": f.name, "size": f.size, "sha": f.sha, "status": "Unchanged"}) for f in manifest_data.files.values()]

        self.show_loading(False)
        self._populate_list()

    def _on_view_mode_changed(self):
        is_all_files_mode = self.view_mode_combo.currentText() == "All Depot Files"
        self.filter_status_combo.setEnabled(not is_all_files_mode)
        if is_all_files_mode:
            self.filter_status_combo.setCurrentText("All Changes")
        self._populate_list()

    def _update_stats_cards(self):
        depot_choice = self.depot_combo.currentText()
        changelog_to_process = None
        manifest_to_process = None

        if depot_choice == "All Depots":
            changelog_to_process = self._merge_depot_data(self.main_changelog_data, self.lang_changelog_data)
            manifest_to_process = self._merge_manifest_data(self.main_manifest_data, self.lang_manifest_data)
        elif depot_choice == "Main":
            changelog_to_process = self.main_changelog_data
            manifest_to_process = self.main_manifest_data
        else:
            changelog_to_process = self.lang_changelog_data
            manifest_to_process = self.lang_manifest_data

        size_diff, file_diff = 0, 0
        if changelog_to_process:
            header = changelog_to_process.get("header_changes", {})
            old_size = int(header.get("total_bytes", {}).get("old", 0))
            new_size = int(header.get("total_bytes", {}).get("new", 0))
            size_diff = new_size - old_size

            old_files = int(header.get("total_files", {}).get("old", 0))
            new_files = int(header.get("total_files", {}).get("new", 0))
            file_diff = new_files - old_files

            source_list = self.all_changelog_files
            main_names = {f.name for f in (self.main_manifest_data.files.values() if self.main_manifest_data else [])}

            if depot_choice == "Main":
                source_list = [f for f in self.all_changelog_files if f.get("name") in main_names]
            elif depot_choice == "Language (eng_us)":
                source_list = [f for f in self.all_changelog_files if f.get("name") not in main_names]

            self.added_card.setValue(str(sum(1 for f in source_list if f['status'] == 'Added')))
            self.removed_card.setValue(str(sum(1 for f in source_list if f['status'] == 'Removed')))
            self.modified_card.setValue(str(sum(1 for f in source_list if f['status'] == 'Modified')))
        else:
            self.added_card.setValue("0")
            self.removed_card.setValue("0")
            self.modified_card.setValue("0")

        new_total_size, new_total_files = 0, 0
        if manifest_to_process:
            self.version_card.setVersion(manifest_to_process.creation_date)
            new_total_files = manifest_to_process.total_files
            new_total_size = manifest_to_process.total_bytes

        self.total_card.setValues(diff=file_diff, new_total=new_total_files)
        self.size_diff_card.setValue(diff=size_diff, new_total=new_total_size)

    def _get_current_source_data(self):
        source_list = self.all_depot_files if self.view_mode_combo.currentText() == "All Depot Files" else self.all_changelog_files
        depot_choice = self.depot_combo.currentText()
        if depot_choice == "All Depots":
            return source_list

        main_names = {f.name for f in (self.main_manifest_data.files.values() if self.main_manifest_data else [])}
        if depot_choice == "Main":
            return [f for f in source_list if f.get("name") in main_names]
        else:
            return [f for f in source_list if f.get("name") not in main_names]

    def _populate_list(self):
        self.list_widget.clear()
        source_data = self._get_current_source_data()

        status_filter = self.filter_status_combo.currentText()
        type_data = self.filter_type_combo.currentData()
        search_text = self.search_bar.text().lower().replace('\\', '/')
        is_all_files_mode = self.view_mode_combo.currentText() == "All Depot Files"

        filtered_files = [
            f for f in source_data
            if (is_all_files_mode or status_filter == "All Changes" or f.get("status") == status_filter) and
               (type_data is None or os.path.splitext(f.get("name", ""))[1].upper().replace('.', '') == type_data) and
               (not search_text or search_text in f.get("name", "").lower().replace('\\', '/'))
        ]

        sorted_files = sorted(filtered_files, key=cmp_to_key(self._changelog_compare))

        type_counts = Counter(os.path.splitext(f.get("name", ""))[1].upper().replace('.', '') for f in source_data if f.get("name"))
        self._populate_type_filter(type_counts)

        for file_info in sorted_files:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, file_info)
            item.setToolTip(file_info.get("name", ""))
            self.list_widget.addItem(item)

        self._update_stats_cards()

    def _populate_type_filter(self, type_counts):
        self.filter_type_combo.blockSignals(True)
        current_selection = self.filter_type_combo.currentData()
        self.filter_type_combo.clear()
        self.filter_type_combo.addItem("All Types", userData=None)
        for type_str, count in sorted(type_counts.items()):
            self.filter_type_combo.addItem(f"{type_str or 'No Ext'} ({count})", userData=type_str)
        index = self.filter_type_combo.findData(current_selection)
        self.filter_type_combo.setCurrentIndex(index if index != -1 else 0)
        self.filter_type_combo.blockSignals(False)

    def _natural_sort_key(self, s: str):
        return [int(text) if text.isdigit() else text for text in re.split('([0-9]+)', s.lower())]

    def _changelog_compare(self, item1: Dict, item2: Dict):
        sort_order = {"Added": 0, "Removed": 1, "Modified": 2, "Unchanged": 3}
        order1 = sort_order.get(item1.get('status'), 4)
        order2 = sort_order.get(item2.get('status'), 4)
        if order1 != order2:
            return -1 if order1 < order2 else 1
        return -1 if self._natural_sort_key(item1.get('name', '')) < self._natural_sort_key(item2.get('name', '')) else 1

    def _update_locate_button_state(self, current, _):
        self.locate_button.setEnabled(current is not None)

    def _locate_selected_file(self):
        if not (item := self.list_widget.currentItem()):
            return
        if not (relative_path := item.data(Qt.UserRole).get("name", "")):
            return

        full_path = os.path.normpath(os.path.join(self.game_root_path, relative_path))
        if os.path.exists(full_path):
            try:
                subprocess.Popen(f'explorer /select,"{full_path}"')
            except Exception as e:
                logger.error(f"Failed to open explorer: {e}", exc_info=True)
                ErrorHandler.handleError(f"An error occurred: {e}")
        else:
            status = item.data(Qt.UserRole).get("status", "")
            if status == "Removed":
                ErrorHandler.handleError("This file was removed in the update and does not exist in your game folder.")
            else:
                ErrorHandler.handleError(f"Could not find the file in your game directory:\n\n{full_path}")

    def _show_context_menu(self, pos):
        if not (item := self.list_widget.itemAt(pos)):
            return

        file_info = item.data(Qt.UserRole)
        relative_path = file_info.get("name", "")
        status = file_info.get("status")
        file_hash = file_info.get("sha", "") if self.view_mode_combo.currentIndex() == 1 else \
                    (file_info.get("changes", {}).get("sha", {}).get("new", "") if status == "Modified" else file_info.get("sha", ""))

        menu = RoundMenu(parent=self)
        full_path = os.path.normpath(os.path.join(self.game_root_path, relative_path))
        full_path_action = QAction(FluentIcon.COPY.icon(), "Copy Path in Game Folder")
        full_path_action.triggered.connect(lambda: QApplication.clipboard().setText(full_path))
        menu.addAction(full_path_action)

        if '/' in relative_path or '\\' in relative_path:
            path_action = QAction(FluentIcon.COPY.icon(), "Copy Relative Path")
            path_action.triggered.connect(lambda: QApplication.clipboard().setText(relative_path))
            menu.addAction(path_action)
            name_action = QAction(FluentIcon.COPY.icon(), "Copy File Name")
            name_action.triggered.connect(lambda: QApplication.clipboard().setText(os.path.basename(relative_path)))
            menu.addAction(name_action)
        else:
            name_action = QAction(FluentIcon.COPY.icon(), "Copy File Name")
            name_action.triggered.connect(lambda: QApplication.clipboard().setText(relative_path))
            menu.addAction(name_action)

        if file_hash:
            menu.addSeparator()
            sha1_action = QAction(FluentIcon.FINGERPRINT.icon(), "Copy SHA1")
            sha1_action.triggered.connect(lambda: QApplication.clipboard().setText(file_hash))
            menu.addAction(sha1_action)

        menu.exec(self.list_widget.mapToGlobal(pos))

    def _merge_depot_data(self, data1: Dict, data2: Dict) -> Dict:
        if not data1: return data2
        if not data2: return data1

        merged = {"header_changes": {}, "added": [], "modified": [], "deleted": []}
        h1 = data1.get("header_changes", {})
        h2 = data2.get("header_changes", {})

        for key in ["total_files", "total_chunks", "total_bytes"]:
            merged["header_changes"][key] = {
                "old": int(h1.get(key, {}).get("old", 0)) + int(h2.get(key, {}).get("old", 0)),
                "new": int(h1.get(key, {}).get("new", 0)) + int(h2.get(key, {}).get("new", 0))
            }

        merged["header_changes"]["creation_date"] = h1.get("creation_date", {})
        for key in ["added", "modified", "deleted"]:
            merged[key] = data1.get(key, []) + data2.get(key, [])

        return merged

    def _merge_manifest_data(self, m1: Optional[Manifest], m2: Optional[Manifest]) -> Optional[Manifest]:
        if not m1: return m2
        if not m2: return m1

        return Manifest(
            depot_id=f"{m1.depot_id}+{m2.depot_id}", manifest_id=f"{m1.manifest_id}+{m2.manifest_id}",
            creation_date=m1.creation_date, total_files=m1.total_files + m2.total_files,
            total_chunks=m1.total_chunks + m2.total_chunks, total_bytes=m1.total_bytes + m2.total_bytes,
            total_compressed_bytes=m1.total_compressed_bytes + m2.total_compressed_bytes, files={**m1.files, **m2.files}
        )

    def closeEvent(self, event):
        for thread, worker in self.threads:
            if thread.isRunning():
                thread.quit()
                thread.wait()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = FilesChangelogWindow(
        game_manager=GameManager(),
        game_root_path="C:\\Program Files (x86)\\Steam\\steamapps\\common\\FC 26",
        game_id="FC26", main_depot_id="3405691", eng_us_depot_id="3405692",
        main_manifest_id="2521253029469654291", eng_us_manifest_id="4559926266552614532",
        update_name="FC26 - Version 1.0.3"
    )
    window.center_window()
    window.show()
    sys.exit(app.exec())