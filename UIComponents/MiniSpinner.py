# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import IndeterminateProgressRing

class MiniSpinner(QWidget):
    """سبينر صغير مناسب للتخطيطات الصغيرة."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spinner = IndeterminateProgressRing(self)

        # إعداد السبينر
        self.spinner.setFixedSize(20, 20)  # حجم صغير
        self.spinner.setCustomBarColor(Qt.white, Qt.white)  # لون أبيض
        self.spinner.setStrokeWidth(2)  # عرض شريط نحيف

        # إضافة السبينر إلى التخطيط
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.spinner, alignment=Qt.AlignCenter)
