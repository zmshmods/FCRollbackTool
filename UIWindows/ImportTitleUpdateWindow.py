import sys
import os
import uuid
from PySide6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QSizePolicy
from PySide6.QtGui import QGuiApplication, QColor
from PySide6.QtCore import Qt
from qframelesswindow import AcrylicWindow
from qfluentwidgets import Theme, setTheme, setThemeColor, IndeterminateProgressBar
from Core.Initializer import MainDataManager, GameManager, AppDataManager, ErrorHandler
from MenuBar.File.ImportTitleUpdate import ImportTitleUpdate, ImportState
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from UIComponents.Personalization import AcrylicEffect
from collections import deque
from Core.Logger import logger

WINDOW_TITLE = "Import Title Update"
WINDOW_SIZE = (420, 220)
THEME_COLOR = "#00FF00"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = False

# Styling constants
WHITE_BOLD = "font-size: 14px; font-weight: bold; color: #FFFFFF;"
GREEN_BOLD = "font-size: 14px; font-weight: bold; color: #00FF00;"
WHTE_NORMAL = "font-size: 14px; color: rgba(255, 255, 255, 0.8);"
GREEN_NORMAL = "font-size: 14px; color: rgba(0, 255, 0, 0.8);"
SEPARATOR_STYLE = {"styleSheet": "background-color: rgba(255, 255, 255, 0.1);", "fixedHeight": 1}

class StateManager:
    """Manages import states and updates the UI."""
    def __init__(self, update_info_label: QLabel, progress_bar: IndeterminateProgressBar):
        self.update_info_label = update_info_label
        self.progress_bar = progress_bar
        self.state_queue = deque()

    def add_state(self, state: ImportState, progress: int, details: str, is_success: bool):
        """Add a state to the queue and process it immediately."""
        self.state_queue.append((state, progress, details, is_success))
        self.process_state_queue()

    def process_state_queue(self):
        """Process the state queue and update the UI."""
        if not self.state_queue:
            return
        state, progress, details, is_success = self.state_queue.popleft()
        self.update_ui(state, progress, details, is_success)

    def update_ui(self, state: ImportState, progress: int, details: str, is_success: bool):
        """Update the UI based on the current state."""
        try:
            if state == ImportState.COMPLETED:  # Changed from IMPORT_COMPLETED to COMPLETED
                self.progress_bar.stop()
                self.update_info_label.setStyleSheet(GREEN_BOLD)
                self.update_info_label.setText(state.value)
            else:
                self.progress_bar.start()
                state_style = WHITE_BOLD
                details_style = GREEN_NORMAL if is_success else WHTE_NORMAL
                details_text = f"<br><span style='{details_style}'>{details}</span>" if details else ""
                self.update_info_label.setStyleSheet("")
                self.update_info_label.setText(
                    f"<span style='{state_style}'>Current Task: {state.value}</span>{details_text}"
                )
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update UI for state {state.value}: {str(e)}")
            raise

class ImportTitleUpdateWindow(AcrylicWindow):
    def __init__(self, input_path: str, parent=None):
        super().__init__(parent=parent)
        self.input_path = input_path
        self.game_mgr = GameManager()
        self.data_mgr = MainDataManager()
        self.app_data_mgr = AppDataManager()
        self.operation_id = str(uuid.uuid4())
        self.import_thread = None
        self.is_completed = False
        self.is_canceled = False
        self.button_manager = ButtonManager(self)
        self.setWindowTitle(WINDOW_TITLE)  
        self.resize(*WINDOW_SIZE)
        AcrylicEffect(self)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setup_ui()
        self.state_manager = StateManager(self.update_info_label, self.progress_bar)

    def closeEvent(self, event):
        """Handle window close event."""
        try:
            if self.import_thread and self.import_thread.isRunning():
                if not self.is_canceled and not self.is_completed:
                    self.import_thread.cancel()
                    self.import_thread.quit()
                    self.import_thread.wait()  # Wait dynamically until thread finishes
            super().closeEvent(event)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to handle close event for ImportTitleUpdateWindow: {str(e)}")

    def setup_ui(self):
        self._setup_title_bar()
        self._setup_main_container()
        self._setup_buttons()

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _setup_title_bar(self):
        title_bar = TitleBar(
            self,
            title=self.windowTitle(),
            icon_path=os.path.join("Data", "Assets", "Icons", "FRICON.png"),
            spacer_width=SPACER_WIDTH,
            show_max_button=SHOW_MAX_BUTTON,
            show_min_button=SHOW_MIN_BUTTON,
            show_close_button=SHOW_CLOSE_BUTTON,
            bar_height=BAR_HEIGHT
        )
        title_bar.create_title_bar()

    def _setup_main_container(self):
        """Set up the transparent container for progress UI."""
        self.main_container = QWidget(
            self,
            styleSheet="background-color: rgba(0, 0, 0, 0.1);",
            sizePolicy=QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        )
        self.main_layout.addWidget(self.main_container)
        self._setup_progress_ui()

    def _setup_progress_ui(self):
        """Set up the progress bar and state label."""
        layout = QVBoxLayout(self.main_container)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(0)
        label_container = QWidget(self.main_container)
        label_container.setStyleSheet("background-color: transparent;")
        label_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        label_layout = QVBoxLayout(label_container)
        label_layout.setContentsMargins(15, 0, 15, 0)
        label_layout.setSpacing(5)
        label_layout.setAlignment(Qt.AlignCenter)
        self.update_info_label = QLabel(
            "",
            alignment=Qt.AlignCenter,
            styleSheet="background-color: transparent;"
        )
        self.update_info_label.setWordWrap(True)
        self.update_info_label.setFixedWidth(400)
        label_layout.addWidget(self.update_info_label)
        self.progress_bar = IndeterminateProgressBar(self)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setCustomBarColor(QColor(THEME_COLOR), QColor(THEME_COLOR))
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.progress_bar.setFixedHeight(5)
        layout.addStretch(1)
        layout.addWidget(label_container)
        layout.addStretch(1)
        layout.addWidget(self.progress_bar)

    def _setup_buttons(self):
        """Set up the Cancel button."""
        self.main_layout.addWidget(QWidget(self, **SEPARATOR_STYLE))
        button_container = self.button_manager.create_buttons()
        self.main_layout.addWidget(button_container or QWidget(self))

    def showEvent(self, event):
        """Start import when window is shown."""
        if self.import_thread is None:
            self.start_import()
        super().showEvent(event)

    def start_import(self):
        """Start the import thread."""
        try:
            self.import_thread = ImportTitleUpdate(
                self.input_path, self.game_mgr, self.data_mgr, self.app_data_mgr, self.operation_id
            )
            self.connect_import_signals()
            self.import_thread.start()
        except ValueError as e:
            ErrorHandler.handleError(f"Failed to start import: {str(e)}")
            self.close()

    def connect_import_signals(self):
        """Connect import thread signals to handlers."""
        try:
            logger.debug(f"Connecting signals for ImportTitleUpdate: {self.input_path}")
            self.import_thread.state_changed.connect(self.state_manager.add_state)
            self.import_thread.completed_signal.connect(self.handle_import_completed)
            self.import_thread.error_signal.connect(self.handle_import_error)
            self.import_thread.cancel_signal.connect(self.handle_import_canceled)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to connect ImportTitleUpdate signals: {str(e)}")
            raise

    def handle_import_completed(self):
        """Handle import completion."""
        try:
            self.is_completed = True
            self.button_manager.update_button_states(completed=True)
            if self.import_thread:
                self.import_thread.quit()
                self.import_thread.wait()  # Wait dynamically until thread finishes
            self.close()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to handle import completion: {str(e)}")

    def handle_import_error(self, error_msg: str):
        """Handle import errors by closing the window."""
        try:
            self.button_manager.update_button_states(error=True)
            if self.import_thread:
                self.import_thread.quit()
                self.import_thread.wait()  # Wait dynamically until thread finishes
            self.close()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to handle import error: {str(e)}")

    def handle_import_canceled(self):
        """Handle user-initiated cancellation."""
        try:
            self.is_canceled = True
            if self.import_thread:
                self.import_thread.quit()
                self.import_thread.wait()  # Wait dynamically until thread finishes
            self.button_manager.update_button_states(canceled=True)
            self.close()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to handle import cancellation: {str(e)}")

class ButtonManager:
    """Manages the Cancel button."""
    def __init__(self, window):
        self.window = window
        self.buttons = {}

    def create_buttons(self):
        """Create the button layout."""
        self._init_buttons()
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.buttons["cancel"])
        button_container = QWidget(self.window)
        button_container.setLayout(button_layout)
        return button_container

    def _init_buttons(self):
        """Initialize the Cancel button."""
        self.buttons["cancel"] = QPushButton("Cancel")
        self.buttons["cancel"].clicked.connect(self.cancel)

    def cancel(self):
        """Cancel the import process."""
        if self.window.import_thread and not self.window.is_canceled:
            self.window.import_thread.cancel()

    def update_button_states(self, completed=False, canceled=False, error=False):
        """Update button states after completion, cancellation, or error."""
        self.buttons["cancel"].setEnabled(not (completed or canceled or error))

# TEST
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = ImportTitleUpdateWindow(r"C:\Users\zmsh\Desktop\ZMSH Tools Projects\FCRollbackTool\Profiles\FC25\TitleUpdates\FC25 - Title Update 2.rar")
    window.show()
    app.exec()

if __name__ == "__main__":
    main()