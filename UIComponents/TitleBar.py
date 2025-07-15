from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy, QWidget
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from qframelesswindow import StandardTitleBar
from UIComponents.Tooltips import apply_tooltip

class TitleBar:
    def __init__(
        self,
        window,
        title: str,
        icon_path: str,
        # Default
        spacer_width: int = 75,
        buttons: dict = None,
        show_max_button: bool = True,
        show_min_button: bool = True,
        show_close_button: bool = True, 
        bar_height: int = 32 
    ):
        self.window = window
        self.title = title
        self.icon_path = icon_path
        self.spacer_width = spacer_width
        self.buttons = buttons or {}
        self.show_max_button = show_max_button
        self.show_min_button = show_min_button
        self.show_close_button = show_close_button
        self.bar_height = bar_height
        self._drag_pos = None
        self.button_widgets = {}
        self.title_label = None  # reference to the title label

    def create_title_bar(self) -> None:
        """Create a customizable title bar."""
        title_bar = StandardTitleBar(self.window)
        self.window.setTitleBar(title_bar)
        title_bar.setDoubleClickEnabled(False)

        if not self.show_max_button:
            title_bar.maxBtn.hide()
        if not self.show_min_button:
            title_bar.minBtn.hide()
        if not self.show_close_button:
            title_bar.closeBtn.hide()

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)

        # Icon
        icon_label = QLabel(self.window)
        icon_label.setPixmap(QPixmap(self.icon_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setFixedSize(24, 24)
        icon_label.setStyleSheet("background-color: transparent;")
        icon_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        layout.addWidget(icon_label)

        # Title
        self.title_label = QLabel(self.title, self.window)  # Store the label for later updates
        self.title_label.setStyleSheet("color: white; font-size: 16px; background-color: transparent;")
        self.title_label.setTextFormat(Qt.RichText)  # Enable Rich Text to support HTML formatting
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.title_label.mousePressEvent = self._start_drag
        self.title_label.mouseMoveEvent = self._drag_window
        layout.addWidget(self.title_label)

        # Custom Buttons
        for name, (text, icon_path, callback, tooltip) in self.buttons.items():
            btn = QPushButton(text, self.window)
            if icon_path:
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(24, 24))
            btn.setFixedHeight(self.bar_height)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color: transparent; border: 0; color: white; }"
                "QPushButton:hover { background-color: rgba(255, 255, 255, 20); }"
                "QPushButton:pressed { background-color: rgba(255, 255, 255, 15); }"
            )
            if callback:
                btn.clicked.connect(callback)
            if tooltip:
                apply_tooltip(btn, tooltip)
            layout.addWidget(btn)
            self.button_widgets[name] = btn

        # Spacers
        layout.addSpacerItem(QSpacerItem(0, self.bar_height, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addSpacerItem(QSpacerItem(self.spacer_width, 0, QSizePolicy.Minimum, QSizePolicy.Minimum))

        self.window.main_layout.setContentsMargins(0, 0, 0, 0)
        self.window.main_layout.addLayout(layout)
        # Separator
        self.window.main_layout.addWidget(QWidget(self.window, styleSheet="background-color: rgba(255, 255, 255, 0.1);", fixedHeight=1))

    def update_title(self, new_title: str) -> None:
        """Update the title text in the QLabel."""
        if self.title_label:
            self.title_label.setText(new_title)
            self.title = new_title  # Update the stored title

    def _start_drag(self, event) -> None:
        """Start dragging the window."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.window.frameGeometry().topLeft()

    def _drag_window(self, event) -> None:
        """Drag the window."""
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.window.move(event.globalPos() - self._drag_pos)