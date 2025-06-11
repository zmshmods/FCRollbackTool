from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from Core.Initializer import ErrorHandler, GITHUB_ACC

def open_guides_url():
    try:
        guides_url = f"https://github.com/{GITHUB_ACC}/FCRollbackTool/wiki/%F0%9F%93%98-Guides"
        QDesktopServices.openUrl(QUrl(guides_url))
    except Exception as e:
        ErrorHandler.handleError(f"Error opening FAQs URL: {e}")
