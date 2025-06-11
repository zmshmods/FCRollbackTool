from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
import sys

def AcrylicEffect(window: QWidget):
    """Disable Acrylic effects based on Windows version."""
    windows_version = sys.getwindowsversion()  # Get Windows version
    if windows_version.major == 10:
        if windows_version.build >= 22000:
            # If >= Windows 11 set AcrylicEffect
            window.windowEffect.setAcrylicEffect(window.winId(), "10101050")
            # window.windowEffect.setMicaEffect(window.winId(), True)
            # window.windowEffect.setAeroEffect(True)
        else:
            # If <= Windows 10 
            # Remove acrylic effect
            window.windowEffect.removeBackgroundEffect(window.winId())

            def paintEvent(event):
                painter = QPainter(window)
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

                painter.setBrush(QColor("#263855"))
                painter.setPen(Qt.NoPen)

                painter.drawRect(window.rect())

                # Add border
                border_pen = QPen(QColor(255, 255, 255, 51))
                border_pen.setWidth(2)
                painter.setPen(border_pen)
                painter.drawRect(window.rect())

                painter.end()

            window.paintEvent = paintEvent
