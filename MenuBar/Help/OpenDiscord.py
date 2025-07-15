from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from Core.ErrorHandler import ErrorHandler

def open_discord_url():
    try:
        discord_url = f"https://discord.gg/HBvjk7aTzp"
        QDesktopServices.openUrl(QUrl(discord_url))
    except Exception as e:
        ErrorHandler.handleError(f"Error opening FAQs URL: {e}")
