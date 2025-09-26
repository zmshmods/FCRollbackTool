import sys
import re
from PySide6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QPushButton
from PySide6.QtGui import QGuiApplication, QIcon, QColor
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import Theme, setTheme, setThemeColor, ProgressRing

from UIComponents.Personalization import BaseWindow
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.MiniSpinner import MiniSpinner

from Core.Logger import logger
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.ErrorHandler import ErrorHandler
from Core.DownloadCore import DownloadCore

# Window Constants
WINDOW_TITLE = "Downloading: {}"
WINDOW_SIZE = (420, 220)
THEME_COLOR = "#00FF00"
ICON_PATH = "Data/Assets/Icons/FRICON.png"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = False

# Style Constants for update_info_label
BOLD_STYLE = "font-size: 16px; font-weight: bold; color: rgba(255, 255, 255, 0.9); background-color: transparent;"
NORMAL_STYLE = "font-size: 14px; color: rgba(255, 255, 255, 0.7); background-color: transparent;"

class DownloadWindow(BaseWindow):
    def __init__(self, update_name, download_url, short_game_name, tab_key, file_name=None, parent=None):
        super().__init__(parent=parent)
        self.update_name = update_name or "Unknown Update"
        self.download_url = download_url
        self.short_game_name = short_game_name
        self.tab_key = tab_key
        self.config_manager = ConfigManager()
        self.game_manager = GameManager()
        self.use_idm = self.config_manager.getConfigKeyAutoUseIDM() and self.config_manager.getConfigKeyIDMPath()
        self.button_manager = ButtonManager(self)
        self.download_thread = None
        self.timer = QTimer(self)
        self.downloaded = 0.0
        self.total = 0.0
        self.rate = "0.00 MB/s"
        self.time_left = "N/A"
        self.connections = "0"
        self.splits = "0"
        self.is_paused = False
        self.download_started = False
        
        self.setWindowTitle(WINDOW_TITLE.format(self.update_name))
        self.resize(*WINDOW_SIZE)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setup_ui()
        self.timer.timeout.connect(self.update_progress)

    def closeEvent(self, event):
        """Handle window close event."""
        try:
            if self.download_thread and not self.download_thread.cancel_flag:
                self.download_thread.cancel()
                self.download_thread.wait()
            super().closeEvent(event)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to handle close event for DownloadWindow: {str(e)}")

    def setup_ui(self):
        self._setup_title_bar()
        self._setup_main_container()
        self._setup_buttons()

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _setup_title_bar(self):
        TitleBar(self, title=self.windowTitle(), icon_path=ICON_PATH, spacer_width=SPACER_WIDTH, 
                 show_max_button=SHOW_MAX_BUTTON, show_min_button=SHOW_MIN_BUTTON, 
                 show_close_button=SHOW_CLOSE_BUTTON, bar_height=BAR_HEIGHT).create_title_bar()

    def _setup_main_container(self):
        self.main_container = QWidget(self, styleSheet="background-color: rgba(0, 0, 0, 0.1);", 
                                            sizePolicy=QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.main_layout.addWidget(self.main_container)
        self._setup_progress_ui()

    def _setup_progress_ui(self):
        self.container_layout = QVBoxLayout(self.main_container)
        self.container_layout.setAlignment(Qt.AlignCenter)

        self.view_stack = QWidget(self.main_container, styleSheet="background-color: transparent;")
        self.stack_layout = QHBoxLayout(self.view_stack)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.addWidget(self.view_stack)

        self.wait_view = QWidget(styleSheet="background-color: transparent;")
        wait_layout = QVBoxLayout(self.wait_view)
        wait_layout.setAlignment(Qt.AlignCenter)
        wait_layout.setSpacing(5)
        wait_layout.setContentsMargins(0,0,0,0)

        spinner_and_title_layout = QHBoxLayout()
        spinner_and_title_layout.setAlignment(Qt.AlignCenter)
        spinner_and_title_layout.setSpacing(10)
        
        self.spinner = MiniSpinner(self.wait_view)
        self.spinner_label = QLabel("Initializing...", self.wait_view, styleSheet=BOLD_STYLE, alignment=Qt.AlignCenter)
        
        spinner_and_title_layout.addWidget(self.spinner)
        spinner_and_title_layout.addWidget(self.spinner_label)

        self.extra_info_label = QLabel("", self.wait_view, styleSheet=NORMAL_STYLE, alignment=Qt.AlignCenter)
        
        wait_layout.addLayout(spinner_and_title_layout)
        wait_layout.addWidget(self.extra_info_label, alignment=Qt.AlignCenter)
        
        self.progress_view = QWidget(styleSheet="background-color: transparent;")
        progress_layout = QHBoxLayout(self.progress_view)
        progress_layout.setSpacing(20)
        progress_layout.setAlignment(Qt.AlignCenter)

        self.info_label = QLabel(self.progress_view, styleSheet="background-color: transparent;", alignment=Qt.AlignLeft | Qt.AlignVCenter)
        self.progress_ring = ProgressRing(self.progress_view)
        self.progress_ring.setValue(0)
        self.progress_ring.setTextVisible(True)
        self.progress_ring.setFixedSize(130, 130)
        self.progress_ring.setCustomBarColor(QColor(THEME_COLOR), QColor(THEME_COLOR))
        
        progress_layout.addWidget(self.info_label)
        progress_layout.addWidget(self.progress_ring)

        self.stack_layout.addWidget(self.wait_view)
        self.stack_layout.addWidget(self.progress_view)
        
        self.update_info_label()

    def _setup_buttons(self):
        self.main_layout.addWidget(QWidget(self, styleSheet="background-color: rgba(255, 255, 255, 0.1);", fixedHeight=1))
        self.main_layout.addWidget(self.button_manager.create_buttons() or QWidget(self))

    def showEvent(self, event):
        self.start_download()
        super().showEvent(event)

    def start_download(self):
        self.download_thread = DownloadCore(self.download_url, self.short_game_name, self.update_name, self.tab_key)
        self.connect_download_signals()
        self.download_thread.start()

    def connect_download_signals(self):
        signals = [
            (self.download_thread.paused_signal, self.on_paused),
            (self.download_thread.resumed_signal, self.on_resumed),
            (self.download_thread.download_completed_signal, self.handle_download_completed),
            (self.download_thread.download_started_signal, self.on_download_started),
            (self.download_thread.progress_signal, self.update_progress_from_signal),
            (self.download_thread.error_signal, self.close),
        ]
        for signal, slot in signals:
            signal.connect(slot)

    def on_download_started(self):
        logger.info("Download started.")
        self.download_started = True
        self.update_info_label()
        if not self.use_idm:
            self.timer.start(100)

    def handle_download_completed(self):
        logger.info("Download completed successfully.")
        self.progress_ring.setValue(100)
        self.update_info_label()
        QTimer.singleShot(1000, self.close)

    def on_paused(self):
        if not self.use_idm:
            logger.info("Download paused.")
            self.is_paused = True
            self.update_info_label()

    def on_resumed(self):
        if not self.use_idm:
            logger.info("Download resumed.")
            self.is_paused = False
            self.update_info_label()

    def update_progress(self):
        if self.download_thread and self.download_thread.cancel_flag:
            self.timer.stop()
            return
        if not self.download_started:
            return
        self.update_info_label()

    def update_progress_from_signal(self, downloaded, total, percentage, rate, eta, connections, splits):
        if not self.use_idm:
            self.downloaded = downloaded
            self.total = total
            self.progress_ring.setValue(int(percentage))
            self.rate = f"{rate:.2f} MB/s"
            self.time_left = self.format_time_left(eta)
            self.connections = str(connections)
            self.splits = str(splits)
            self.button_manager.update_button_states()
            self.update_info_label()

    def format_time_left(self, eta):
        hours, minutes, seconds = 0, 0, 0
        if 'h' in eta:
            hours_match = re.search(r'(\d+)h', eta)
            if hours_match:
                hours = int(hours_match.group(1))
                eta = eta.replace(f"{hours}h", "")
        if 'm' in eta:
            minutes_match = re.search(r'(\d+)m', eta)
            if minutes_match:
                minutes = int(minutes_match.group(1))
                eta = eta.replace(f"{minutes}m", "")
        seconds_match = re.search(r'(\d+)s', eta)
        if seconds_match:
            seconds = int(seconds_match.group(1))
        return " ".join([f"{h}h" for h in [hours] if h] + [f"{m}m" for m in [minutes] if m] + [f"{s}s" for s in [seconds] if s]) or "N/A"

    def update_info_label(self, cancelling=False):
        if cancelling and not self.use_idm:
            self.progress_view.hide()
            self.spinner.show()
            self.spinner_label.setText("Cancelling...")
            self.extra_info_label.hide()
            self.wait_view.show()
            return

        if self.use_idm:
            self.progress_view.hide()
            self.spinner.show()
            self.spinner_label.setText("Waiting for IDM to complete...")
            self.extra_info_label.setText("It will be in the profile folder once completed.")
            self.extra_info_label.show()
            self.wait_view.show()
        else:
            if self.total > 0:
                self.wait_view.hide()
                self.info_label.setText(
                    f"<div>"
                    f"<span style='{BOLD_STYLE}'>Current Task: {'Paused' if self.is_paused else 'Downloading' if self.progress_ring.value() < 100 else 'Completed'}</span><br>"
                    f"<span style='{NORMAL_STYLE}'>"
                    f"Downloaded: {self.downloaded:.2f} MB / {self.total:.2f} MB<br>"
                    f"Transfer Rate: {self.rate}<br>"
                    f"Time Left: {self.time_left}<br>"
                    f"Splits: {self.splits}<br>"
                    f"Connections: {self.connections}"
                    f"</span></div>"
                )
                self.progress_view.show()
            else:
                self.progress_view.hide()
                self.spinner.show()
                self.spinner_label.setText("Initializing Download, Please Wait...")
                self.extra_info_label.hide()
                self.wait_view.show()

class ButtonManager:
    def __init__(self, window):
        self.window = window
        self.button_container = None
        self.buttons = {}

    def create_buttons(self):
        self._init_buttons()
        self._setup_layout()
        self.button_container = QWidget(self.window)
        self.button_container.setLayout(self.button_layout)
        return self.button_container

    def close(self):
        if self.window.download_thread:
            self.window.download_thread.cancel()
            self.window.download_thread.quit()
            self.window.download_thread.wait()
        self.window.close()

    def cancel(self):
        if self.window.download_thread and not self.window.use_idm:
            self.window.update_info_label(cancelling=True)
            self.window.download_thread.cancel_status_signal.connect(
                lambda status: self.window.close() if status == "canceled" else None
            )
            self.window.download_thread.cancel()

    def toggle_pause(self):
        if self.window.download_thread and not self.window.use_idm:
            if not self.window.is_paused and self.window.downloaded > 0.0:
                self.window.download_thread.pause()
                self.window.is_paused = True
                self.buttons["pause"].hide()
                self.buttons["resume"].show()
            elif self.window.is_paused:
                self.window.download_thread.resume()
                self.window.is_paused = False
                self.buttons["pause"].show()
                self.buttons["resume"].hide()
            self.window.update_info_label()

    def update_button_states(self):
        if self.window.downloaded == 0.0:
            self.buttons["pause"].setEnabled(False)
            self.buttons["resume"].setEnabled(False)
        else:
            self.buttons["pause"].setEnabled(True)
            self.buttons["resume"].setEnabled(True)

    def _init_buttons(self):
        button_configs = {
            "pause": (" Pause", self.toggle_pause, QIcon("Data/Assets/Icons/ic_fluent_Pause_24_regular.png")),
            "resume": (" Start", self.toggle_pause, QIcon("Data/Assets/Icons/ic_fluent_play_24_regular.png")),
            "cancel": ("Cancel", self.cancel, None),
            "close": ("Close Window", self.close, None)
        }
        for name, (text, func, icon) in button_configs.items():
            btn = QPushButton(text)
            btn.clicked.connect(func)
            if icon:
                btn.setIcon(icon)
            self.buttons[name] = btn
        self.buttons["resume"].hide()
        if self.window.use_idm:
            self.buttons["pause"].hide()
            self.buttons["resume"].hide()
            self.buttons["cancel"].hide()
        else:
            self.buttons["close"].hide()
            self.update_button_states()

    def _setup_layout(self):
        self.button_layout = QHBoxLayout()
        if not self.window.use_idm:
            self.button_layout.addStretch()
            self.button_layout.addWidget(self.buttons["cancel"])
            self.button_layout.addWidget(self.buttons["pause"]) 
            self.button_layout.addWidget(self.buttons["resume"])
        else:
            self.button_layout.addStretch()
            self.button_layout.addWidget(self.buttons["close"])

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    app.setWindowIcon(QIcon(ICON_PATH))
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = DownloadWindow("FC25 - Title Update 2", "https://www.mediafire.com/file/9f9jg3r3smhdoqj/OriginSetup.exe/file", "FC25", "TitleUpdates")
    window.show()
    app.exec()

if __name__ == "__main__":
    main()