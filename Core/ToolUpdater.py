import requests, webbrowser, ctypes, importlib.resources, sys
import os
import configparser
from datetime import datetime, timedelta
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import setTheme, setThemeColor, Theme
from qframelesswindow import AcrylicWindow, StandardTitleBar
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtCore import Qt
from UIComponents.AcrylicEffect import AcrylicEffect
from Core.Logger import logger
from UIComponents.MainStyles import MainStyles

ToolVersion = "1.1 Beta"
UpdateManifest = "https://raw.githubusercontent.com/zmshmods/FCRollbackToolUpdates/main/toolupdate.json"
ChangelogBaseURL = "https://raw.githubusercontent.com/zmshmods/FCRollbackToolUpdates/main/Changelogs/"

def check_for_updates():
    """Check if the tool version matches the version in the UpdateManifest."""
    try:
        response = requests.get(UpdateManifest, timeout=10)
        response.raise_for_status()
        data = response.json()
        latest_version = data.get("ToolUpdate", {}).get("ToolVersion", "Unknown Version")

        # إذا لم يتطابق الإصدار الحالي مع الإصدار الأحدث
        if latest_version != ToolVersion:
            return latest_version  # أعد الإصدار الجديد
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
    return None


class UpdateWindow(AcrylicWindow):
    def __init__(self, new_version=None, parent=None):
        super().__init__(parent)
        self.new_version = new_version  # تخزين الإصدار الجديد
        self.setWindowTitle(f"New update available")
        self.resize(450, 200)
        AcrylicEffect(self)
        self.features = []  # قائمة لحفظ الميزات
        self.download_link = None  # رابط التنزيل
        self.data_dir = os.path.join(os.getenv("LOCALAPPDATA"), "FC_Rollback_Tool", "Data")
        self.timer_file = os.path.join(self.data_dir, "reminder_timer.ini")  # تم تغيير الاسم هنا
        self.center_window()
        self.setup_ui()  # إعداد واجهة المستخدم مباشرةً


    def fetch_update_version(self):
        """Fetch the latest version from the UpdateManifest."""
        try:
            response = requests.get(UpdateManifest, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.new_version = data.get("ToolUpdate", {}).get("ToolVersion", "Unknown Version")
            self.download_link = data.get("ToolUpdate", {}).get("DownloadLink", None)  # تخزين رابط التنزيل
        except Exception as e:
            logger.error(f"Error fetching update version: {e}")
            self.new_version = "Unknown Version"
            self.download_link = None

    def fetch_changelog(self):
        """Fetch the changelog for the new version."""
        try:
            if self.new_version:
                # تكوين الرابط بناءً على الإصدار الجديد
                changelog_url = f"{ChangelogBaseURL}{self.new_version}.txt"
                response = requests.get(changelog_url, timeout=10)  # طلب الملف النصي
                response.raise_for_status()
                
                # قراءة جميع الأسطر وتحليلها
                lines = response.text.splitlines()
                
                # إزالة الشرطات من بداية كل سطر وإضافة النصوص إلى القائمة
                self.features = [line.lstrip("-").strip() for line in lines if line.strip()]
        except Exception as e:
            logger.error(f"Error fetching changelog.")
            self.features = ["Unable to fetch changelog."]

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        x = (screen.width() - window_geometry.width()) // 2
        y = (screen.height() - window_geometry.height()) // 2
        self.move(x, y)

    def create_title_bar(self):
        try:
            title_bar = StandardTitleBar(self)
            self.setTitleBar(title_bar)
            for btn in [title_bar.closeBtn, title_bar.maxBtn, title_bar.minBtn]: btn.hide()
            title_bar.setDoubleClickEnabled(False)
            self.title_bar_container = QWidget(self)
            self.title_bar_container.setStyleSheet("background-color: transparent;")
            self.title_bar_container.setFixedHeight(32)
            self.title_bar_container.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            title_bar_layout = QHBoxLayout(self.title_bar_container)
            title_bar_layout.setContentsMargins(10, 0, 10, 0)
            self.title_label = QLabel(self.windowTitle(), self)
            self.title_label.setStyleSheet("color: white; font-size: 16px;")
            self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            title_bar_layout.addWidget(self.title_label)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.addWidget(self.title_bar_container)
            separator = QWidget(self)
            separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
            separator.setFixedHeight(1)
            self.main_layout.addWidget(separator)
        except Exception as e:
            self.handle_error(f"Error creating title bar: {e}")

    def setup_ui(self):
        try:
            self.fetch_update_version()  # استدعاء الدالة لجلب الإصدار الجديد
            self.fetch_changelog()  # استدعاء الدالة لجلب قائمة الميزات
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 5)
            self.create_title_bar()
            self.create_transparent_container()
            self.create_buttons()
            self.main_layout.setSpacing(0)
        except Exception as e:
            self.handle_error(f"Error setting up UI: {e}")

    def create_transparent_container(self):
        try:
            # إنشاء الحاوية الشفافة
            self.transparent_container = QWidget(self)
            self.transparent_container.setStyleSheet("background-color: rgba(0, 0, 0, 0);")
            self.transparent_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            container_layout = QVBoxLayout(self.transparent_container)
            container_layout.setContentsMargins(10, 5, 10, 0)
            container_layout.setAlignment(Qt.AlignTop)

            # نص الإصدار الجديد مع الميزات في نفس العنصر
            main_label_text = f"FC Rollback Tool {self.new_version} - (What's new):<br>"
            features_text = "".join([f"\u2022 {feature}<br>" for feature in self.features])
            combined_text = f"<div style='font-size: 16px; color: white; background-color: transparent; text-align: left;'>{main_label_text}{features_text}</div>"

            # إنشاء عنصر QLabel للعرض
            main_label = QLabel(combined_text, self)
            main_label.setStyleSheet("font-size: 16px; color: white; background-color: transparent;")
            main_label.setAlignment(Qt.AlignLeft)
            container_layout.addWidget(main_label)

            # Spacer مرن لدفع باقي العناصر إلى الأعلى
            spacer = QWidget(self)
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            container_layout.addWidget(spacer)

            # نص الإصدار الحالي (في الأسفل دائمًا)
            additional_label = QLabel(
                f"Your current version: {ToolVersion}<br>It's recommended to always use the latest version", self
            )
            additional_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.5);")
            additional_label.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(additional_label, alignment=Qt.AlignHCenter)

            self.main_layout.addWidget(self.transparent_container)
        except Exception as e:
            self.handle_error(f"Error creating transparent container: {e}")


    def create_buttons(self):
        try:
            self.Skip_button = QPushButton("Remind Me Later")
            self.Update_button = QPushButton("Update Now")

            # ربط زر "Update Now" بفتح الرابط
            self.Update_button.clicked.connect(self.open_download_link)

            # ربط زر "Remind Me Later" بتخزين الوقت وإغلاق النافذة
            self.Skip_button.clicked.connect(self.remind_me_later)

            button_layout = QHBoxLayout()
            button_layout.addStretch()
            button_layout.addWidget(self.Skip_button)
            button_layout.addWidget(self.Update_button)
            separator = QWidget(self)
            separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
            separator.setFixedHeight(1)
            self.main_layout.addWidget(separator)
            self.ButtonContainer = QWidget(self)
            self.ButtonContainer.setLayout(button_layout)
            self.main_layout.addWidget(self.ButtonContainer)
        except Exception as e:
            self.handle_error(f"Error creating buttons: {e}")

    def remind_me_later(self):
        """تخزين الوقت الحالي وإصدار التحديث في ملف INI وإغلاق النافذة."""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            config = configparser.ConfigParser()
            config["REMINDERTIMER"] = {
                "LastSkipTime": datetime.now().isoformat(),
                "LastSkippedVersion": self.new_version  # تخزين إصدار التحديث
            }
            with open(self.timer_file, "w") as configfile:
                config.write(configfile)
            print(f"The tool update is skipped for now {datetime.now()}")
        except Exception as e:
            self.handle_error(f"Error saving remind me later time: {e}")
        self.close()

        
    def open_download_link(self):
        """Open the download link in the default web browser and close the tool."""
        if self.download_link:
            webbrowser.open(self.download_link)  # فتح الرابط في المتصفح
            QApplication.quit()  # إغلاق الأداة بعد فتح الرابط
        else:
            ctypes.windll.user32.MessageBoxW(0, "Download link not available.", "Info", 0x10)
            logger.error(f"Download link not available")


    def handle_error(self, message):
        logger.error(message)
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)


def should_show_update():
    """التحقق مما إذا كان يجب عرض نافذة التحديث بناءً على الإصدار المخزن والوقت."""
    data_dir = os.path.join(os.getenv("LOCALAPPDATA"), "FC_Rollback_Tool", "Data")
    timer_file = os.path.join(data_dir, "reminder_timer.ini")

    latest_version = check_for_updates()  # جلب أحدث إصدار

    if not latest_version:
        return False  # إذا لم يتم جلب الإصدار الجديد، لا حاجة لعرض التحديث

    if os.path.exists(timer_file):
        try:
            config = configparser.ConfigParser()
            config.read(timer_file)
            LastSkipTime_str = config.get("REMINDERTIMER", "LastSkipTime", fallback=None)
            LastSkippedVersion = config.get("REMINDERTIMER", "LastSkippedVersion", fallback=None)

            # إذا كان الإصدار الجديد مختلفًا عن المخزن، عرض النافذة بغض النظر عن الوقت
            if latest_version != LastSkippedVersion:
                return True

            # إذا كان الإصدار الجديد نفسه، تحقق من الوقت
            if LastSkipTime_str:
                LastSkipTime = datetime.fromisoformat(LastSkipTime_str)
                if datetime.now() - LastSkipTime < timedelta(hours=24):
                    return False  # لا حاجة لعرض النافذة إذا كان الوقت لم ينتهِ
        except Exception as e:
            print(f"Error reading ReminderTimer: {e}")

    return True  # عرض النافذة إذا لم يتم تخطيها أو إذا كان هناك خطأ


def main():
    try:
        app = QApplication(sys.argv)
        app.setStyleSheet(MainStyles())
        setTheme(Theme.DARK)
        setThemeColor("#00FF00")

        if should_show_update():
            main_window = UpdateWindow()
            main_window.show()

        return app.exec()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Error", 0x10)


if __name__ == "__main__":
    main()
