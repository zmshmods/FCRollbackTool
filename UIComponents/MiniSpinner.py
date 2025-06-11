from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from qfluentwidgets import IndeterminateProgressRing

class MiniSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spinner = IndeterminateProgressRing(self)

        self.spinner.setFixedSize(20, 20)
        self.spinner.setCustomBarColor(Qt.white, Qt.white)
        self.spinner.setStrokeWidth(2)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.spinner, alignment=Qt.AlignCenter)

class MiniSpinnerForButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spinner = IndeterminateProgressRing(self)
        self.spinner.setFixedSize(20, 20)
        self.spinner.setCustomBarColor(Qt.white, Qt.white)
        self.spinner.setStrokeWidth(2)
        self.spinner.move(4, 4)  # Adjust position to fit within the button
        self.spinner.hide()

    def setSpinnerVisible(self, visible: bool):
        self.spinner.setVisible(visible)
        if visible:
            self.spinner.start()
        else:
            self.spinner.stop()