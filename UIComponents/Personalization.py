import sys
from qframelesswindow import AcrylicWindow, FramelessWindow
from PySide6.QtCore import Qt
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

    def updateFrameless(self):
        """Override to force FramelessWindowHint on PySide6 >= 6.10.
        
        qframelesswindow 0.8.1 uses Qt.NoTitleBarBackgroundHint for PySide6 >= 6.10
        (to fix issue #206), but this causes native system buttons to remain visible
        alongside the custom StandardTitleBar buttons, resulting in duplicate
        minimize/maximize/close buttons.
        """
        stayOnTop = Qt.WindowStaysOnTopHint if self.windowFlags() & Qt.WindowStaysOnTopHint else 0
        self.setWindowFlags(Qt.FramelessWindowHint | stayOnTop)

        self.windowEffect.enableBlurBehindWindow(self.winId())
        self.windowEffect.addWindowAnimation(self.winId())

        if isWin11:
            self.windowEffect.setAcrylicEffect(self.winId())
            self.windowEffect.addShadowEffect(self.winId())