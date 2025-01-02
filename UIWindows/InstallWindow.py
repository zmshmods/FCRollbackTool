# --------------------------------------- Standard Libraries ---------------------------------------
import sys, ctypes, psutil, re
# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import setTheme, setThemeColor, Theme, ProgressBar
from qframelesswindow import AcrylicWindow, StandardTitleBar
from PySide6.QtGui import QGuiApplication, QColor
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QCoreApplication
# --------------------------------------- Project-Specific Imports ---------------------------------------
from UIComponents.AcrylicEffect import AcrylicEffect
from UIComponents.Tooltips import apply_tooltip
from Core.Logger import logger
from Core.InstallThread import InstallThread

class InstallWindow(AcrylicWindow):
    update_progress_signal = Signal(int)
    update_message_signal = Signal(str)
    update_file_name_signal = Signal(str)
    update_log_signal = Signal(str)

    def __init__(self, selected_game_path, update_name, table_component=None, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(f"Installing Update: {update_name}")
        self.setFixedSize(420, 220)
        AcrylicEffect(self)
        self.selected_game_path, self.update_name, self.table_component = selected_game_path, update_name, table_component
        self.setup_ui()
        self.start_installation()
        self.center_window()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_installation_progress)
        self.timer.start(100)

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 5, 0, 5)
        self.create_title_bar()
        self.create_transparent_container()
        self.create_buttons()
        self.main_layout.setSpacing(0)
        setTheme(Theme.DARK)
        setThemeColor("#00FF00")
        self.connect_signals()

    def create_title_bar(self):
        try:
            title_bar = StandardTitleBar(self)
            self.setTitleBar(title_bar)
            title_bar.closeBtn.hide()
            title_bar.maxBtn.hide()
            title_bar.minBtn.hide()
            title_bar.setDoubleClickEnabled(False)
            self.title_bar_container = self.setup_title_bar_container(title_bar)
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
        return container

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
        layout = QVBoxLayout(self.transparent_container)
        layout.setAlignment(Qt.AlignCenter)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setValue(1)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setCustomBarColor(QColor("#00FF00"), QColor("#00FF00"))
        self.progress_bar.setFixedSize(250, 5)
        self.message_label = QLabel("<span style='font-size: 12px; color: rgba(255, 255, 255, 0.7);'>Current Task: Installing...</span>")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.message_label)

    def create_buttons(self):
        try:
            button_layout = QHBoxLayout()
            self.hide_button = QPushButton("Hide")
            self.force_close_button = QPushButton("Force-Close and Retry")
            self.force_close_button.setVisible(False)
            self.force_close_button.clicked.connect(self.force_close_and_retry)
            button_layout.addStretch()
            button_layout.addWidget(self.force_close_button)
            button_layout.addWidget(self.hide_button)
            self.hide_button.clicked.connect(self.close_window)
            self.add_separator()
            self.ButtonContainer = QWidget(self)
            self.ButtonContainer.setLayout(button_layout)
            self.main_layout.addWidget(self.ButtonContainer)
        except Exception as e:
            self.handle_error(f"Error creating buttons: {e}")

    def add_separator(self):
        separator = QWidget(self)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
        separator.setFixedHeight(1)
        self.main_layout.addWidget(separator)

    def start_installation(self):
        running_processes = InstallThread.get_running_processes()
        if running_processes:
            process_list = "<br>".join([f"<b>{name}</b> with PID: {pid}" for name, pid in running_processes])
            self.message_label.setText(
                f"<span style='color:white;'>Processes blocking installation:</span><br>{process_list}"
            )
            self.force_close_button.setVisible(True)
            return  # إيقاف بدء التثبيت إذا كانت العمليات قيد التشغيل
        if hasattr(self, 'install_thread') and self.install_thread.is_alive():
            logger.warning("Installation is already in progress.")
            return
        self.install_thread = InstallThread(self.selected_game_path, self.update_name, parent=self)
        self.connect_thread_signals()
        self.progress_bar.setVisible(True)
        self.install_thread.start()


    def connect_thread_signals(self):
        signals = [self.update_progress_signal, self.update_message_signal, self.update_file_name_signal, self.update_log_signal]
        for signal, thread_signal in zip(signals, [self.install_thread.update_progress, self.install_thread.update_message, self.install_thread.update_file_name, self.install_thread.update_log]):
            thread_signal.connect(signal.emit)

    def connect_signals(self):
        signals = [self.update_progress_signal, self.update_message_signal, self.update_file_name_signal, self.update_log_signal]
        slots = [self.update_progress, self.update_message, self.update_file_name, self.update_log]
        for signal, slot in zip(signals, slots):
            signal.connect(slot)

    @Slot(int)
    def update_progress(self, progress):
        if progress < 100:
            self.progress_bar.setValue(progress)
        else:
            self.progress_bar.setValue(100)
            self.progress_bar.setVisible(True)
            QTimer.singleShot(1000, self.close_window)

    @Slot(str)
    def update_message(self, message):
        self.message_label.setText(message)
        self.force_close_button.setVisible("Process(es) blocking the installation" in message)
        self.raise_()

    @Slot(str)
    def update_file_name(self, file_name):
        self.message_label.setText(f"Current Task: {file_name}")
        self.raise_()

    @Slot(str)
    def update_log(self, log_message):
        self.message_label.setText(f"<span style='font-size: 12px; color: rgba(255, 255, 255, 0.7);'>Current Task: {log_message}</span>")
        self.raise_()

    def check_installation_progress(self):
        QCoreApplication.processEvents()

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        x = (screen.width() - window_geometry.width()) // 2
        y = (screen.height() - window_geometry.height()) // 2
        self.move(x, y)

    def close_window(self):
        self.close()

    def force_close_and_retry(self):
        try:
            message_text = self.message_label.text()
            running_processes = []

            # استخدام تعبير منتظم لاستخراج الأسماء و PIDs
            pattern = r"<b>(.+?)</b> with PID: (\d+)"
            matches = re.findall(pattern, message_text)

            for process_name, pid in matches:
                try:
                    psutil.Process(int(pid)).terminate()
                    logger.info(f"Terminated process: {process_name} (PID: {pid})")
                except Exception as e:
                    logger.error(f"Failed to terminate process {process_name} (PID: {pid}): {e}")

            self.force_close_button.setVisible(False)
            self.message_label.setText("<span style='color:white;'>Retrying installation...</span>")
            QTimer.singleShot(1000, self.start_installation)
        except Exception as e:
            self.handle_error(f"Error during force-close and retry: {e}")


    def handle_error(self, message):
        logger.error(message)
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)

def main():
    try:
        app = QApplication(sys.argv)
        setTheme(Theme.DARK)
        setThemeColor("#00FF00")
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Error", 0x10)