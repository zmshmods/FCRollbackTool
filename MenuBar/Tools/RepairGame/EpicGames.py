# --------------------------------------- Standard Libraries ---------------------------------------
import sys, importlib.resources, ctypes, winreg, psutil, os
# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import setTheme, setThemeColor, Theme
from qframelesswindow import AcrylicWindow, StandardTitleBar
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt
# --------------------------------------- Project-Specific Imports ---------------------------------------
from UIComponents.AcrylicEffect import AcrylicEffect
from UIComponents.Tooltips import apply_tooltip
from Core.Logger import logger
# ----------------------------------- نافذة تطبيق Epic Games -----------------------------------
class EpicGamesWindow(AcrylicWindow):
    def __init__(self, parent=None):
        self.config_cache = None
        super().__init__(parent=parent)
        self.setWindowTitle("Repair Game - Epic Games")  # عنوان النافذة
        self.resize(370, 100)  # حجم النافذة
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)  # تثبيت النافذة أعلى النوافذ الأخرى
        AcrylicEffect(self)  # تأثير الأكريليك
        self.center_window()  # ضبط الموقع
        self.manage_epicgames()  # إدارة تشغيل التطبيق
        self.setup_ui()  # إعداد الواجهة

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
            title_bar.maxBtn.hide()
            title_bar.minBtn.hide()
            title_bar.setDoubleClickEnabled(False)

            self.title_bar_container = QWidget(self)
            self.title_bar_container.setStyleSheet("background-color: transparent;")
            self.title_bar_container.setFixedHeight(32)
            self.title_bar_container.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            title_bar_layout = QHBoxLayout(self.title_bar_container)
            title_bar_layout.setContentsMargins(10, 0, 10, 0)

            self.title_label = QLabel(self.windowTitle(), self)
            self.title_label.setStyleSheet("color: white; background-color: transparent; font-size: 16px;")
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
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 5)
            self.create_title_bar()
            self.create_transparent_container()
            self.main_layout.setSpacing(0)
        except Exception as e:
            self.handle_error(f"Error setting up UI: {e}")

    def manage_epicgames(self):
        """إدارة تشغيل تطبيق Epic Games Launcher"""
        try:
            pid = next((proc.info['pid'] for proc in psutil.process_iter(['pid', 'name']) if proc.info['name'] == "EpicGamesLauncher.exe"), None)

            if pid:
                logger.info(f"Epic Games Launcher is running (PID: {pid}). Terminating...")
                process = psutil.Process(pid)
                if process.is_running():
                    process.terminate()
                    process.wait(timeout=10)
                    logger.info(f"Epic Games Launcher (PID: {pid}) terminated successfully.")
                else:
                    logger.warning(f"Epic Games Launcher (PID: {pid}) is not running.")

                logger.info("Restarting Epic Games Launcher after termination...")
                app_path = self.get_epicgames_path()
                if app_path and os.path.exists(app_path):
                    os.startfile(app_path)
                    logger.info(f"Epic Games Launcher started successfully from: {app_path}")
                else:
                    logger.error("Failed to find Epic Games Launcher executable path for restarting.")
            else:
                logger.info("Epic Games Launcher is not running. Starting application...")
                app_path = self.get_epicgames_path()
                if app_path and os.path.exists(app_path):
                    os.startfile(app_path)
                    logger.info(f"Epic Games Launcher started successfully from: {app_path}")
                else:
                    logger.error("Failed to find Epic Games Launcher executable path.")
        except Exception as e:
            logger.error(f"Error managing Epic Games Launcher: {e}")

    def get_epicgames_path(self):
        """الحصول على مسار Epic Games Launcher من الريجستري"""
        try:
            registry_path = r"SOFTWARE\WOW6432Node\Epic Games\EOS\InstallHelper"
            registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path)
            path, _ = winreg.QueryValueEx(registry_key, "Path")
            base_path = path.replace(r"\Epic Online Services\EpicOnlineServicesInstallHelper.exe", "")
            full_path = base_path + r"\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe"
            return full_path
        except FileNotFoundError:
            logger.error("Epic Games registry key not found.")
            return None

    def create_transparent_container(self):
        try:
            # إنشاء الحاوية الشفافة
            self.transparent_container = QWidget(self)
            self.transparent_container.setStyleSheet("background-color: rgba(0, 0, 0, 0.1);")  # تحديد اللون الشفاف
            self.transparent_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # جعل الحاوية قابلة للتوسيع
            layout = QVBoxLayout(self.transparent_container)  # إعداد تخطيط للحاوية الشفافة
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)  # محاذاة النصوص إلى الأعلى واليسار

            # التعليمات
            steps = """
            <p style="color: white; font-size: 14px; font-weight: bold; white-space: nowrap;">
            1. Go to library.<br>
            2. Click the three-dot menu below the game's image.<br>
            3. Select Manage.<br>
            4. Click on "Verify Files" button.
            </p>
            """

            # إنشاء QLabel للتعليمات
            steps_label = QLabel(steps, self)
            steps_label.setStyleSheet("background-color: transparent;")  # جعل خلفية النص شفافة
            steps_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # محاذاة النص إلى الأعلى واليسار
            steps_label.setWordWrap(False)  # تعطيل تغليف النص

            # إضافة QLabel للتعليمات
            layout.addWidget(steps_label)

            # الرسالة الإضافية
            additional_message = QLabel(
                "It may take some time to repair, you can close this window.",
                self
            )
            additional_message.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 12px; background-color: transparent;")
            additional_message.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # محاذاة النص إلى الأعلى واليسار

            # إضافة الرسالة الإضافية إلى الحاوية
            layout.addWidget(additional_message)

            # إضافة الحاوية إلى التخطيط الرئيسي
            self.main_layout.addWidget(self.transparent_container)
        except Exception as e:
            self.handle_error(f"Error creating transparent container: {e}")

    def handle_error(self, message):
        logger.error(message)
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)

# ----------------------------------- الدالة الرئيسية -----------------------------------
def main():
    try:
        app = QApplication(sys.argv)
        with importlib.resources.open_text('UIComponents', 'Styles.qss', encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        setTheme(Theme.DARK)
        setThemeColor("#00FF00")
        main_window = EpicGamesWindow()
        main_window.show()
        return app.exec()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Error", 0x10)

if __name__ == "__main__":
    main()
