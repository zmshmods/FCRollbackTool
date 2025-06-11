from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from Core.Initializer import ErrorHandler, GITHUB_ACC

def open_faqs_url():
    try:
        faqs_url = f"https://github.com/{GITHUB_ACC}/FCRollbackTool/wiki/%E2%9D%93-Frequently-Asked-Questions-(FAQs)"
        QDesktopServices.openUrl(QUrl(faqs_url))
    except Exception as e:
        ErrorHandler.handleError(f"Error opening FAQs URL: {e}")
