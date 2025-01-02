from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
import sys

def AcrylicEffect(window: QWidget):
    """تعطيل التأثيرات بناءً على إصدار ويندوز مع إضافة بوردير للنافذة بلون ثابت"""
    windows_version = sys.getwindowsversion()  # جلب إصدار الويندوز
    if windows_version.major == 10:
        if windows_version.build >= 22000:
            # إذا كان النظام ويندوز 11 أو أحدث
            window.windowEffect.setAcrylicEffect(window.winId(), "10101050")
            # window.windowEffect.setMicaEffect(window.winId(), True) 
            # window.windowEffect.setAeroEffect(True)
            
        else:
            # إذا كان النظام ويندوز 10 أو أقدم
            # إزالة التأثير الأكريليك
            window.windowEffect.removeBackgroundEffect(window.winId())  # إزالة التأثير الأكريليك

            # رسم الخلفية باستخدام اللون الثابت
            def paintEvent(event):
                painter = QPainter(window)
                painter.setRenderHint(QPainter.Antialiasing, True)  # تحسين جودة الرسومات
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)  # تحسين التحويلات في الصور

                # تعيين اللون الثابت للخلفية
                painter.setBrush(QColor("#263855"))  # اللون الأزرق الثابت
                painter.setPen(Qt.NoPen)  # عدم رسم الحدود للداخل

                # رسم الخلفية باستخدام اللون الثابت
                painter.drawRect(window.rect())  # رسم مستطيل يغطي كامل النافذة

                # إضافة حدود (بوردير)
                border_pen = QPen(QColor(255, 255, 255, 51))
                border_pen.setWidth(2)  # سمك الحدود 
                painter.setPen(border_pen)  # تعيين القلم للرسم
                painter.drawRect(window.rect())  # رسم الحدود حول النافذة

                painter.end()

            # تعيين الدالة للرسم في النافذة
            window.paintEvent = paintEvent
