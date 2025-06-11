from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import IndeterminateProgressRing

class LoadingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spinner = IndeterminateProgressRing(self)
        self.spinner.setFixedSize(60, 60)
        self.spinner.setStrokeWidth(5)
        self.spinner.setCustomBarColor(Qt.white, Qt.white)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.spinner)