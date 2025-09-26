import sys
import os
from PySide6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QSizePolicy
from PySide6.QtGui import QGuiApplication, QColor
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import Theme, setTheme, setThemeColor, ProgressBar
from Core.InstallCore import InstallCore, InstallState
from UIComponents.Personalization import BaseWindow
from UIComponents.MainStyles import MainStyles
from UIComponents.TitleBar import TitleBar
from collections import deque

from Core.Logger import logger
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.ErrorHandler import ErrorHandler

WINDOW_TITLE = "Installing Update"
WINDOW_SIZE = (420, 220)
THEME_COLOR = "#00FF00"
SPACER_WIDTH = 75
BAR_HEIGHT = 32
SHOW_MAX_BUTTON = False
SHOW_MIN_BUTTON = False
SHOW_CLOSE_BUTTON = False

TITLE_STYLE = "font-size: 14px; font-weight: bold; color: #FFFFFF;"
TITLE_GREEN_STYLE = "font-size: 14px; font-weight: bold; color: #00FF00;"
OPTIONS_STYLE = "font-size: 14px; font-weight: bold; color: #FFFF00;"
DISC_STYLE = "font-size: 14px; color: rgba(255, 255, 255, 0.8);"
FILE_NAMES_STYLE = "font-size: 14px; color: #00FF00;"

SEPARATOR_STYLE = {"styleSheet": "background-color: rgba(255, 255, 255, 0.1);", "fixedHeight": 1}

class StateManager:
    """Manages installation states and updates the UI."""
    def __init__(self, update_info_label: QLabel, progress_bar: ProgressBar):
        self.update_info_label = update_info_label
        self.progress_bar = progress_bar
        self.state_queue = deque()
        self.current_progress = 0

    def add_state(self, state: InstallState, progress: int, details: str):
        """Add a state to the queue and process it immediately."""
        self.state_queue.append((state, progress, details))
        self.process_state_queue()

    def process_state_queue(self):
        """Process the state queue and update the UI."""
        if not self.state_queue:
            return
        state, progress, details = self.state_queue.popleft()
        self.update_ui(state, progress, details)

    def update_ui(self, state: InstallState, progress: int, details: str):
        """Update the UI based on the current state."""
        try:
            # Update progress bar for specific states
            if state in (InstallState.INSTALLING_FILES, InstallState.INSTALLING_SQUADS, InstallState.INSTALLING_FUT_SQUADS):
                self.current_progress = progress
                self.progress_bar.setValue(self.current_progress)

            # Determine label style and progress
            if state == InstallState.INSTALLATION_COMPLETED:
                style = TITLE_GREEN_STYLE
                progress_value = 100
                text = f"<span style='{style}'>{state.value}</span><br>" \
                    f"<span style='{DISC_STYLE}'>{details}</span>"
            else:
                style = OPTIONS_STYLE if state in (
                    InstallState.PREPARING,
                    InstallState.BACKING_UP_SETTINGS,
                    InstallState.BACKING_UP_TITLE_UPDATE,
                    InstallState.DELETING_STORED_TITLE_UPDATE,
                    InstallState.DELETING_SQUAD_FILES,
                    InstallState.DELETING_LIVE_TUNING_UPDATE
                ) else TITLE_STYLE
                progress_value = 100 if state == InstallState.INSTALLATION_COMPLETED else self.current_progress
                details_style = FILE_NAMES_STYLE if state == InstallState.INSTALLING_FILES and details and not details.endswith('%') else DISC_STYLE
                text = f"<span style='{TITLE_STYLE}'>Current Task: </span>" \
                    f"<span style='{style}'>{state.value}</span><br>" \
                    f"<span style='{details_style}'>{details}</span>"

            self.progress_bar.setValue(progress_value)
            self.update_info_label.setText(text)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to update UI for state {state.value}: {str(e)}")
            raise

class InstallWindow(BaseWindow):
    def __init__(self, update_name: str, tab_key: str, game_path: str, file_path: str, table_component=None, parent=None):
        super().__init__(parent=parent)
        self.update_name = update_name
        self.tab_key = tab_key
        self.game_path = game_path
        self.file_path = file_path
        self.table_component = table_component  # Store table_component for signal connection
        self.config_mgr = ConfigManager()
        self.game_mgr = GameManager()
        self.button_manager = ButtonManager(self)
        self.install_thread = None
        self.is_completed = False
        self.is_canceled = False
        self.setWindowTitle(f"{WINDOW_TITLE}: {self.update_name}")
        self.resize(*WINDOW_SIZE)
        self.center_window()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setup_ui()
        self.state_manager = StateManager(self.update_info_label, self.progress_bar)
        self.setWindowModality(Qt.ApplicationModal)

    def closeEvent(self, event):
        """Handle window close event."""
        try:
            if self.install_thread and not self.is_canceled and not self.is_completed:
                self.install_thread.cancel()
                self.install_thread.wait()
            super().closeEvent(event)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to handle close event for InstallWindow: {str(e)}")

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
        label_layout.setContentsMargins(0, 0, 0, 0)
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
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setValue(0)
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
        """Start installation when window is shown."""
        if self.install_thread is None:
            self.start_installation()
        super().showEvent(event)

    def start_installation(self):
        """Start the installation thread."""
        try:
            self.install_thread = InstallCore(self.update_name, self.tab_key, self.game_path, self.file_path)
            self.connect_install_signals()
            self.install_thread.start()
        except ValueError as e:
            ErrorHandler.handleError(f"Failed to start installation: {str(e)}")
            self.close()

    def connect_install_signals(self):
        """Connect installation thread signals to handlers."""
        try:
            logger.debug(f"Connecting signals for InstallCore: {self.update_name}")
            self.install_thread.state_changed.connect(self.state_manager.add_state)
            self.install_thread.completed_signal.connect(self.handle_install_completed)
            self.install_thread.error_signal.connect(self.handle_install_error)
            self.install_thread.cancel_signal.connect(self.handle_install_canceled)
            # Connect request_table_update signal if table_component is provided and tab_key is TitleUpdates
            if (self.table_component and 
                self.tab_key == self.game_mgr.getTabKeyTitleUpdates() and 
                hasattr(self.table_component, 'update_table')):
                self.install_thread.request_table_update.connect(self.table_component.update_table)
                logger.debug(f"Connected request_table_update signal for {self.tab_key}")
        except Exception as e:
            ErrorHandler.handleError(f"Failed to connect InstallCore signals: {str(e)}")
            raise

    def handle_install_completed(self):
        self.is_completed = True
        self.button_manager.update_button_states(completed=True)
        QTimer.singleShot(1000, self.close)  

    def handle_install_error(self, error_msg: str):
        """Handle installation errors by closing the window."""
        self.button_manager.update_button_states(error=True)
        self.close()

    def handle_install_canceled(self):
        """Handle user-initiated cancellation."""
        self.is_canceled = True
        if self.install_thread:
            self.install_thread.quit()
            self.install_thread.wait()
        self.button_manager.update_button_states(canceled=True)
        self.close()

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
        """Cancel the installation process."""
        if self.window.install_thread and not self.window.is_canceled:
            self.window.install_thread.cancel()

    def update_button_states(self, completed=False, canceled=False, error=False):
        """Update button states after completion, cancellation, or error."""
        self.buttons["cancel"].setEnabled(False)

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MainStyles())
    setTheme(Theme.DARK)
    setThemeColor(THEME_COLOR)
    window = InstallWindow("Test Update", "TitleUpdates", r"C:\Program Files (x86)\Steam\steamapps\common\EA SPORTS FC 25", r"C:\Users\zmsh\Desktop\ZMSH Tools Projects\FCRollbackTool\Profiles\FC25\TitleUpdates\FC25 - Title Update 1")
    window.show()
    app.exec()

if __name__ == "__main__":
    main()