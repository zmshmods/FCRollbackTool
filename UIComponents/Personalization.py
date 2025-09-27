import sys
from qframelesswindow import AcrylicWindow, FramelessWindow
from PySide6.QtGui import QPalette, QColor
isWin11 = sys.platform == 'win32' and sys.getwindowsversion().build >= 22000
WinBase = AcrylicWindow if isWin11 else FramelessWindow

class BaseWindow(WinBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        if isWin11:
            self.windowEffect.setAcrylicEffect(self.winId(), "10101050")
            # window.windowEffect.setMicaEffect(window.winId(), True)
            # window.windowEffect.setAeroEffect(True)
            # window.windowEffect.removeBackgroundEffect(window.winId())
        else:

            self.setAutoFillBackground(True)
            palette = self.palette()
            palette.setColor(QPalette.Window, QColor("#2c2c2c"))
            self.setPalette(palette)