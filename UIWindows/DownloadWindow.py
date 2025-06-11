import sys
import os
import re
from PySide6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QPushButton
from PySide6.QtGui import QGuiApplication, QIcon, QColor
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import Theme, setTheme, setThemeColor, ProgressRing
from qframelesswindow import AcrylicWindow
from Core.Logger import logger
from Core.DownloadCore import DownloadCore
from Core.Initializer import AppDataManager, ErrorHandler, ConfigManager, GameManager
from UIComponents.Personalization import AcrylicEffect
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.MiniSpinner import MiniSpinner

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

class DownloadWindow(AcrylicWindow):
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
        AcrylicEffect(self)
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
        layout = QHBoxLayout(self.main_container)
        spinner_info_layout = QVBoxLayout()
        spinner_layout = QHBoxLayout()
        
        self.spinner = MiniSpinner(self.main_container)
        self.spinner_label = QLabel("Initializing Download, Please Wait...", self.main_container, 
                                   styleSheet=BOLD_STYLE, alignment=Qt.AlignCenter)
        
        spinner_layout.addWidget(self.spinner, alignment=Qt.AlignVCenter)
        spinner_layout.addWidget(self.spinner_label, alignment=Qt.AlignVCenter)
        spinner_layout.setSpacing(10)
        spinner_layout.setContentsMargins(0, 0, 0, 0)
        
        self.info_label = QLabel(self.main_container, styleSheet="background-color: transparent;", 
                                alignment=Qt.AlignLeft | Qt.AlignVCenter)
        self.extra_info_label = QLabel(self.main_container, styleSheet=NORMAL_STYLE + " background-color: transparent;",
                                      alignment=Qt.AlignLeft | Qt.AlignVCenter)
        self.extra_info_label.hide()
        
        spinner_info_layout.addLayout(spinner_layout)
        spinner_info_layout.addWidget(self.info_label)
        spinner_info_layout.addWidget(self.extra_info_label)
        spinner_info_layout.setSpacing(0)
        spinner_info_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_ring = ProgressRing(self.main_container)
        self.progress_ring.setValue(0)
        self.progress_ring.setTextVisible(True)
        self.progress_ring.setFixedSize(130, 130)
        self.progress_ring.setCustomBarColor(QColor(THEME_COLOR), QColor(THEME_COLOR))

        layout.addLayout(spinner_info_layout)
        layout.addWidget(self.progress_ring)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)
        
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
            self.spinner.hide()
            self.spinner_label.hide()
            self.info_label.setText(f"<span style='{BOLD_STYLE}'>Cancelling...</span>")
            self.extra_info_label.hide()
            self.progress_ring.hide()
        else:
            if self.use_idm:
                self.spinner.show()
                self.spinner_label.show()
                self.spinner_label.setText("Waiting for IDM to complete...")
                self.info_label.setText("")
                self.extra_info_label.setText("It will be in the profile folder once completed.")
                self.extra_info_label.show()
                self.progress_ring.hide()
            else:
                if self.total > 0:  # Show progress when total size is known
                    self.spinner.hide()
                    self.spinner_label.hide()
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
                    self.extra_info_label.hide()
                    self.progress_ring.show()
                else:  
                    self.spinner.show()
                    self.spinner_label.show()
                    self.spinner_label.setText("Initializing Download, Please Wait...")
                    self.info_label.setText("")
                    self.extra_info_label.hide()
                    self.progress_ring.hide()

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
            self.download_thread.cancel()
            self.download_thread.quit()
            self.download_thread.wait()
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