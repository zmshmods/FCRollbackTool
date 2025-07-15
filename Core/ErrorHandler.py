import win32api
import win32con
from Core.Logger import logger

class ErrorHandler:
    ERR_TITLE = "FC Rollback Tool - Error"

    @staticmethod
    def handleError(message: str) -> None:
        logger.error(message)
        win32api.MessageBox(0, message, ErrorHandler.ERR_TITLE, win32con.MB_OK | win32con.MB_ICONERROR)