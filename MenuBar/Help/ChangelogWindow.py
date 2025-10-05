import sys
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QStackedWidget)
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtCore import Qt, QObject, QThread, Signal, QTimer

from qfluentwidgets import Theme, setTheme, setThemeColor, ComboBox, ScrollArea, BodyLabel

from UIComponents.Personalization import BaseWindow
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.Spinner import LoadingSpinner

from Core.Logger import logger
from Core.ToolUpdateManager import ToolUpdateManager
from Core.ErrorHandler import ErrorHandler

WINDOW_TITLE = "Changelog"
WINDOW_SIZE = (720, 480)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/ic_fluent_code_24_filled.png"
SEPARATOR_STYLE = "background-color: rgba(255, 255, 255, 0.1);"

class ChangelogFetcher(QObject):
    versions_ready = Signal(list)
    changelog_ready = Signal(str, list)

    def __init__(self, tool_update_manager: ToolUpdateManager):
        super().__init__()
        self.tool_update_manager = tool_update_manager

    def fetch_versions(self):
        versions = self.tool_update_manager.get_all_versions()
        self.versions_ready.emit(versions)

    def fetch_changelog(self, version: str):
        changelog = self.tool_update_manager.get_changelog_for_version(version)
        self.changelog_ready.emit(version, changelog)


class ChangelogWindow(BaseWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.tool_update_manager = ToolUpdateManager()
        self._initialize_window()

    def _initialize_window(self):
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*WINDOW_SIZE)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setup_ui()
        QTimer.singleShot(100, self._start_initial_fetch)

    def setup_ui(self) -> None:
        try:
            self._setup_title_bar()
            self._setup_main_container()
        except Exception as e:
            ErrorHandler.handleError(f"Error setting up UI: {e}")

    def center_window(self) -> None:
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _setup_title_bar(self) -> None:
        title_bar = TitleBar(self, title=WINDOW_TITLE, icon_path=ICON_PATH)
        title_bar.create_title_bar()

    def _setup_main_container(self) -> None:
        self.main_container = QWidget(self)
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(15, 10, 15, 10)
        container_layout.setSpacing(10)

        top_layout = QHBoxLayout()
        self.title_label = BodyLabel("FC Rollback Tool")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        top_layout.addWidget(self.title_label)
        top_layout.addStretch()

        self.version_combo = ComboBox(self)
        self.version_combo.setMinimumWidth(150)
        self.version_combo.setFixedHeight(28)
        self.version_combo.setEnabled(False)
        self.version_combo.currentTextChanged.connect(self._on_version_selected)
        top_layout.addWidget(self.version_combo)
        
        container_layout.addLayout(top_layout)
        container_layout.addWidget(QWidget(self, styleSheet=SEPARATOR_STYLE, fixedHeight=1))

        self.stack = QStackedWidget(self)
        container_layout.addWidget(self.stack)

        loading_widget = QWidget()
        loading_layout = QVBoxLayout(loading_widget)
        loading_layout.setAlignment(Qt.AlignCenter)
        loading_layout.setSpacing(10)
        loading_layout.addWidget(LoadingSpinner(self))
        loading_label = QLabel("Loading...", self)
        loading_label.setAlignment(Qt.AlignCenter)
        loading_layout.addWidget(loading_label)
        self.stack.addWidget(loading_widget)
        
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background: transparent; border: none;")
        self.changelog_content_widget = QWidget()
        self.changelog_layout = QVBoxLayout(self.changelog_content_widget)
        self.changelog_layout.setContentsMargins(5, 5, 5, 5)
        self.changelog_layout.setSpacing(5)
        self.changelog_layout.addStretch()
        scroll_area.setWidget(self.changelog_content_widget)
        self.stack.addWidget(scroll_area)

        self.main_layout.addWidget(self.main_container)
        self.stack.setCurrentIndex(0)

    def _start_initial_fetch(self):
        self.fetcher_thread = QThread()
        self.fetcher = ChangelogFetcher(self.tool_update_manager)
        self.fetcher.moveToThread(self.fetcher_thread)
        self.fetcher.versions_ready.connect(self._on_versions_ready)
        self.fetcher.changelog_ready.connect(self._on_changelog_ready)
        self.fetcher_thread.started.connect(self.fetcher.fetch_versions)
        self.fetcher_thread.start()

    def _on_versions_ready(self, versions: list):
        current_version = self.tool_update_manager.getToolVersion()
        if current_version in versions:
            versions.remove(current_version)
        versions.insert(0, current_version)
        self.title_label.setText(f"FC Rollback Tool v{current_version}")
        self.version_combo.blockSignals(True)
        self.version_combo.addItems(versions)
        self.version_combo.setCurrentText(current_version)
        self.version_combo.setEnabled(True)
        self.version_combo.blockSignals(False)
        self.fetcher.fetch_changelog(current_version)

    def _on_version_selected(self, version: str):
        if self.version_combo.signalsBlocked() or not version:
            return
        self.stack.setCurrentIndex(0)
        self.fetcher.fetch_changelog(version)

    def _on_changelog_ready(self, version: str, changelog: list):
        if self.version_combo.currentText() == version:
            self.title_label.setText(f"FC Rollback Tool v{version}")
            self._update_changelog_display(changelog)
            self.stack.setCurrentIndex(1)
    
    def _update_changelog_display(self, changelog_lines: list):
        while self.changelog_layout.count() > 1:
            item = self.changelog_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for line in changelog_lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            if stripped_line.startswith("- *"):
                changelog_label = QLabel(f"Note: {stripped_line[3:].strip()}")
                changelog_label.setStyleSheet("font-size: 14px; color: yellow; background-color: transparent;")
            else:
                changelog_label = QLabel(f"• {stripped_line[1:].strip() if stripped_line.startswith('-') else stripped_line}")
                changelog_label.setStyleSheet("font-size: 14px; color: white; background-color: transparent;")
            changelog_label.setWordWrap(True)
            self.changelog_layout.insertWidget(self.changelog_layout.count() - 1, changelog_label)

    def closeEvent(self, event):
        if hasattr(self, 'fetcher_thread') and self.fetcher_thread.isRunning():
            self.fetcher_thread.quit()
            self.fetcher_thread.wait()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = ChangelogWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    main()