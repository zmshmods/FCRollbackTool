# --------------------------------------- Standard Libraries ---------------------------------------
import math
# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import IndeterminateProgressRing

class LoadingSpinner(QWidget):  # نفس اسم الكلاس الأصلي
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0  # زاوية الدوران (لتحكم الحركة)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.setVisible(True)  # السبينر مرئي
        self.timer.start(16)  # تحديث أسرع قليلاً لتحسين السلاسة

        # استبدال IndeterminateProgressRing
        self.spinner = IndeterminateProgressRing(self)

        # ضبط حجم السبينر
        self.spinner.setFixedSize(60, 60)

        # تغيير لون السبينر إلى الأبيض
        self.spinner.setCustomBarColor(Qt.white, Qt.white)

        # نضيف السبينر إلى التخطيط بشكل واضح
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.spinner, 0, Qt.AlignCenter)

        # عامل الزمن للتحكم في تسريع وتبطيء الحركة
        self.time_factor = 0

        # اجعل السبينر أنحف
        self.spinner.setStrokeWidth(4)  # ضبط عرض الشريط ليصبح نحيفًا

    def rotate(self):  # نفس اسم الدالة الأصلية
        # استخدام دالة cos لتسريع وتبطيء حركة السبينر بشكل أكثر تدريجية واحترافية
        easing_speed = (1 + math.cos(self.time_factor)) * 2  # تأثير cos لتسريع وتبطيء أكثر سلاسة
        self.time_factor += 0.03  # زيادة تدريجية أبطأ للتحكم في الحركة بمرور الوقت

        # تعديل سرعة الدوران بناءً على التباطؤ والتسارع
        self.angle += easing_speed * 3  # تعديل السرعة لجعل الحركة أكثر سلاسة وبطيئة
        if self.angle >= 360:
            self.angle = 0

        self.spinner.update()  # تحديث السبينر مع الحركة الجديدة
        self.update()  # إعادة رسم الواجهة

    def paintEvent(self, event):  # نفس اسم الدالة الأصلية
        # نترك رسم السبينر للـ IndeterminateProgressRing
        super().paintEvent(event)