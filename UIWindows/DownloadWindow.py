# --------------------------------------- Standard Libraries ---------------------------------------
import sys, ctypes, re, os
# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import setTheme, setThemeColor, Theme, ProgressRing
from qframelesswindow import AcrylicWindow, StandardTitleBar
from PySide6.QtGui import QGuiApplication, QIcon, QColor
from PySide6.QtCore import Qt, QThread, QTimer
# --------------------------------------- Project-Specific Imports ---------------------------------------
from UIComponents.AcrylicEffect import AcrylicEffect
from UIComponents.Tooltips import apply_tooltip
from Core.Logger import logger
from Core.DownloadThread import DownloadThread  
from UIComponents.MiniSpinner import MiniSpinner

class DownloadWindow(AcrylicWindow):
    def __init__(self, update_name, download_url, short_game_name, file_name=None, parent=None):
        super().__init__(parent=parent)
        self.update_name = update_name or "Unknown Update"
        self.download_url, self.short_game_name = download_url, short_game_name
        self.setWindowTitle(f"Downloading: {self.update_name}")
        self.resize(420, 220)
        AcrylicEffect(self)
        self.center_window()
        self.setup_ui()
        
        self.download_thread = None
        self.log_file_path = self.create_log_file()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.downloaded = 0.0  # قيم افتراضية
        self.total = 0.0      # قيم افتراضية
        self.rate = "N/A"     # قيمة افتراضية
        self.time_left = "N/A"  # قيمة افتراضية
        self.connections = 0  # قيمة افتراضية
        self.is_Paused = False
        
    def showEvent(self, event):
        self.start_download()
        super().showEvent(event)

    def start_download(self):
        self.download_thread = DownloadThread(self.download_url, self.short_game_name, self.update_name)
        self.connect_download_signals()
        self.download_thread.start()
        self.timer.start(100)

    def connect_download_signals(self):
        signals = [self.download_thread.paused_signal, self.download_thread.resumed_signal, 
                   self.download_thread.download_completed_signal]
        slots = [self.on_paused, self.on_resumed, self.handle_download_completed]
        for signal, slot in zip(signals, slots):
            signal.connect(slot)

    def cancel_download(self):
        if self.download_thread:
            self.update_info_label(cancelling=True)
            QApplication.processEvents()
            self.download_thread.cancel_status_signal.connect(
                lambda status: self.spinner.show() if status == "canceling" else self.close()
            )
            self.download_thread.cancel()

    def handle_download_completed(self):
        logger.info("Download completed. Closing the window.")
        self.progress_ring.setValue(100)
        QTimer.singleShot(1000, self.close)

    def on_paused(self):
        logger.info("Download paused by user.")

    def on_resumed(self):
        logger.info("Download resumed by user.")

    def center_window(self):
        screen, window = QGuiApplication.primaryScreen().geometry(), self.geometry()
        self.move((screen.width() - window.width()) // 2, (screen.height() - window.height()) // 2)

    def create_title_bar(self):
        try:
            title_bar = StandardTitleBar(self)
            self.setTitleBar(title_bar)
            title_bar.closeBtn.hide()
            title_bar.maxBtn.hide()
            title_bar.minBtn.hide()
            title_bar.setDoubleClickEnabled(False)
            self.setup_title_bar_container(title_bar)
        except Exception as e:
            self.handle_error(f"Error creating title bar: {e}")

    def setup_title_bar_container(self, title_bar):
        container = QWidget(self)
        container.setStyleSheet("background-color: transparent;")
        container.setFixedHeight(32)
        container.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 0, 10, 0)
        self.title_label = QLabel(self.windowTitle(), self)
        self.title_label.setStyleSheet("color: white; font-size: 16px;")
        self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.title_label)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(container)
        self.add_separator()

    def setup_ui(self):
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 5)
            self.create_title_bar()
            self.create_transparent_container()
            self.create_buttons()
            self.main_layout.setSpacing(0)
        except Exception as e:
            self.handle_error(f"Error setting up UI: {e}")

    def create_transparent_container(self):
        try:
            self.transparent_container = QWidget(self)
            self.transparent_container.setStyleSheet("background-color: rgba(0, 0, 0, 0.1);")
            self.transparent_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.main_layout.addWidget(self.transparent_container)
            self.setup_progress_ui()
        except Exception as e:
            self.handle_error(f"Error creating transparent container: {e}")

    def setup_progress_ui(self):
        layout = QHBoxLayout(self.transparent_container)
        spinner_layout = QHBoxLayout()
        self.info_label = QLabel(self.transparent_container)
        self.info_label.setStyleSheet("background-color: transparent; font-size: 16px; color: rgba(255, 255, 255, 0.9);")
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.spinner = MiniSpinner(self.transparent_container)
        self.spinner.hide()
        spinner_layout.addWidget(self.spinner, alignment=Qt.AlignVCenter)
        spinner_layout.addWidget(self.info_label, alignment=Qt.AlignVCenter)
        spinner_layout.setSpacing(5)
        spinner_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_ring = ProgressRing(self.transparent_container)
        self.progress_ring.setValue(0)
        self.progress_ring.setTextVisible(True)
        self.progress_ring.setFixedSize(130, 130)
        self.progress_ring.setCustomBarColor(QColor("#00FF00"), QColor("#00FF00"))

        layout.addLayout(spinner_layout)
        layout.addWidget(self.progress_ring)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)
        self.update_info_label(default=True)

    def update_progress(self):
        try:
            if self.download_thread and self.download_thread.cancel_flag:
                logger.info("Progress update aborted due to cancellation.")
                self.cleanup_log_file()
                self.timer.stop()
                return

            if os.path.exists(self.log_file_path):
                with open(self.log_file_path, 'r') as file:
                    lines = file.readlines()
                    if lines:  # تحقق إذا كان هناك سطور في الملف
                        last_line = lines[-1].strip()
                        self.parse_log_line(last_line)
                        self.update_info_label()
        except Exception as e:
            logger.error(f"Error updating progress: {e}")

    def parse_log_line(self, line):
        matches = [re.search(pattern, line) for pattern in [
            r'(\d+\.?\d*)([KMG]iB)/', r'/(\d+\.?\d*)([KMG]iB)\(', r'\((\d+)%\)', 
            r'DL:(\d+\.?\d*)([KMG]iB)', r'ETA:(\d+m\d+s|\d+m|\d+s)', r'CN:(\d+)'
        ]]
        
        if all(matches[:3]):  # Checking if the first three matches are found
            self.downloaded = self.convert_to_mb(*matches[0].groups())
            self.total = self.convert_to_mb(*matches[1].groups())
            self.progress_ring.setValue(int(matches[2].group(1)))
            self.rate = f"{self.convert_to_mb(*matches[3].groups()):.2f} MB/s" if matches[3] else "N/A"
            self.time_left = matches[4].group(1) if matches[4] else "N/A"
            self.connections = int(matches[5].group(1)) if matches[5] else 0


    def convert_to_mb(self, value, unit):
        return float(value) * (1024 if unit == "GiB" else 1/1024 if unit == "KiB" else 1)

    def update_info_label(self, default=False, cancelling=False):
        if cancelling:
            self.info_label.setText("<span style='font-size: 16px; font-weight: bold; color: rgba(255, 255, 255, 0.9);'>Cancelling...</span>")
            self.spinner.show()
            self.progress_ring.hide()
        elif default:
            self.info_label.setText("<div style='display: flex; align-items: center;'><span style='font-size: 16px; font-weight: bold; color: rgba(255, 255, 255, 0.9);'>Waiting for download info...</span></div>")
            self.spinner.show()
            self.progress_ring.hide()
        else:
            status_text = "Paused" if self.is_Paused else "Downloading..."
            self.info_label.setText(f"<div><span style='font-size: 16px; font-weight: bold; color: rgba(255, 255, 255, 0.9);'>Current Task: {status_text}</span><br><span style='font-size: 14px; color: rgba(255, 255, 255, 0.7);'>Downloaded: {self.downloaded:.2f} MB / {self.total:.2f} MB<br>Transfer Rate: {self.rate}<br>Time Left: {self.time_left}<br>Connections: {self.connections} Active</span></div>")
            self.spinner.hide()
            self.progress_ring.show()

    def create_buttons(self):
        try:
            self.Pause_button = self.create_button("Data/Assets/Icons/ic_fluent_Pause_24_regular.png", " Pause")
            self.Start_button = self.create_button("Data/Assets/Icons/ic_fluent_play_24_regular.png", " Start")
            self.cancel_button = QPushButton("Cancel", self)

            self.Pause_button.clicked.connect(self.toggle_Pause_Start)
            self.Start_button.clicked.connect(self.toggle_Pause_Start)
            self.cancel_button.clicked.connect(self.cancel_download)

            self.Start_button.hide()

            button_layout = QHBoxLayout()
            button_layout.addStretch()
            button_layout.addWidget(self.Pause_button)
            button_layout.addWidget(self.Start_button)
            button_layout.addWidget(self.cancel_button)

            self.add_separator()
            self.ButtonContainer = QWidget(self)
            self.ButtonContainer.setLayout(button_layout)
            self.main_layout.addWidget(self.ButtonContainer)
        except Exception as e:
            self.handle_error(f"Error creating buttons: {e}")

    def create_button(self, icon_path, text):
        button = QPushButton(self)
        button.setFixedWidth(80)
        button.setIcon(QIcon(icon_path))
        button.setText(text)
        return button

    def toggle_Pause_Start(self):
        if self.download_thread:
            if not self.is_Paused:
                if self.downloaded == 0:
                    return
                self.download_thread.pause()
                self.is_Paused = True
                self.Pause_button.setVisible(False)
                self.Start_button.setVisible(True)
            else:
                self.download_thread.resume()
                self.is_Paused = False
                self.Pause_button.setVisible(True)
                self.Start_button.setVisible(False)
            self.update_info_label()

    def create_log_file(self):
        temp_folder = os.path.join(os.getenv("LOCALAPPDATA"), "FC_Rollback_Tool", "Temp")
        os.makedirs(temp_folder, exist_ok=True)
        return os.path.join(temp_folder, f"Download_{self.update_name}.log")

    def cleanup_log_file(self):
        if self.log_file_path and os.path.exists(self.log_file_path):
            try:
                os.remove(self.log_file_path)
                logger.info(f"Log file {self.log_file_path} released and deleted after cancellation.")
            except Exception as e:
                logger.error(f"Failed to release log file during cancellation: {e}")

    def add_separator(self):
        separator = QWidget(self)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
        separator.setFixedHeight(1)
        self.main_layout.addWidget(separator)

    def handle_error(self, message):
        logger.error(message)
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)