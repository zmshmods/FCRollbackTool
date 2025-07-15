import win32api
import win32con
from Core.Logger import logger

class NotificationHandler:
    INFO_TITLE = "FC Rollback Tool - Information"
    WARNING_TITLE = "FC Rollback Tool - Warning"
    CONFIRM_TITLE = "FC Rollback Tool - Confirmation"

    @staticmethod
    def showInfo(message: str) -> None:
        logger.info(message)
        win32api.MessageBox(0, message, NotificationHandler.INFO_TITLE, win32con.MB_OK | win32con.MB_ICONINFORMATION)

    @staticmethod
    def showWarning(message: str) -> None:
        logger.warning(message)
        win32api.MessageBox(0, message, NotificationHandler.WARNING_TITLE, win32con.MB_OK | win32con.MB_ICONWARNING)

    @staticmethod
    def showConfirmation(message: str) -> str:
        response = win32api.MessageBox(0, message, NotificationHandler.CONFIRM_TITLE, win32con.MB_YESNOCANCEL | win32con.MB_ICONQUESTION)
        if response == win32con.IDYES:
            return "Yes"
        elif response == win32con.IDNO:
            return "No"
        return "Cancel"