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
# ----------------------------------- مفتاح الاداة -----------------------------------
class EAAppWindow(AcrylicWindow):
    # إعدادات النافذة
    def __init__(self, parent=None):
        self.config_cache = None
        super().__init__(parent=parent)
        self.setWindowTitle("Repair Game - EA App")  # تعيين عنوان النافذة
        self.resize(370, 100)   # تحديد حجم النافذة
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)  # تثبيت النافذة أعلى النوافذ الأخرى
        AcrylicEffect(self)  # تفعيل أو تعطيل تأثير الأكريليك بناءً على نوع الويندوز
        self.center_window()  # ضبط موقع النافذة في وسط الشاشة
        self.manage_eadesktop()  # استدعاء المنطق أثناء إنشاء النافذة
        self.setup_ui()  # إعداد واجهة المستخدم
    # وظيفة لضبط موقع النافذة في وسط الشاشة
    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()  # الحصول على أبعاد الشاشة
        window_geometry = self.geometry()  # الحصول على أبعاد النافذة
        x = (screen.width() - window_geometry.width()) // 2  # حساب المسافة الأفقية لضبط المركز
        y = (screen.height() - window_geometry.height()) // 2  # حساب المسافة الرأسية لضبط المركز
        self.move(x, y)  # نقل النافذة إلى الموقع المحسوب
    def create_title_bar(self):
        try:
            # استخدام StandardTitleBar كما هو
            title_bar = StandardTitleBar(self)
            self.setTitleBar(title_bar)
            title_bar.maxBtn.hide()
            title_bar.minBtn.hide()
            # تعطيل التفاعل مع شريط العنوان
            title_bar.setDoubleClickEnabled(False)

            # إنشاء حاوية لشريط العنوان
            self.title_bar_container = QWidget(self)
            self.title_bar_container.setStyleSheet("background-color: transparent;")  # لون الخلفية
            self.title_bar_container.setFixedHeight(32)  # تحديد ارتفاع شريط العنوان
            self.title_bar_container.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # عدم اعتراض الماوس
            
            # إنشاء تخطيط أفقي لشريط العنوان
            title_bar_layout = QHBoxLayout(self.title_bar_container)
            title_bar_layout.setContentsMargins(10, 0, 10, 0)  # الهوامش الداخلية
            
            # إنشاء عنوان النافذة
            self.title_label = QLabel(self.windowTitle(), self)
            self.title_label.setStyleSheet("color: white; background-color: transparent; font-size: 16px;")
            self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)  # محاذاة العنوان يسار ووسط رأسيًا
            self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            # إضافة العنوان إلى التخطيط
            title_bar_layout.addWidget(self.title_label)
            
            # إضافة الحاوية إلى التخطيط الرئيسي
            self.main_layout.setContentsMargins(0, 0, 0, 0)  # إزالة الهوامش من التخطيط الرئيسي
            self.main_layout.addWidget(self.title_bar_container)
            
            # إضافة خط فاصل تحت شريط العنوان
            separator = QWidget(self)
            separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
            separator.setFixedHeight(1)
            self.main_layout.addWidget(separator)

        except Exception as e:
            self.handle_error(f"Error creating title bar: {e}")

    # إعداد واجهة المستخدم
    def setup_ui(self):
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 5)
            self.create_title_bar()  # إنشاء شريط العنوان
            self.create_transparent_container()  # إنشاء الحاوية الشفافة مع التعليمات
            self.main_layout.setSpacing(0)
        except Exception as e:
            self.handle_error(f"Error setting up UI: {e}")

    def manage_eadesktop(self):
        """إدارة تشغيل تطبيق EA Desktop"""
        try:
            # التحقق مما إذا كان EA Desktop قيد التشغيل
            pid = next((proc.info['pid'] for proc in psutil.process_iter(['pid', 'name']) if proc.info['name'] == "EADesktop.exe"), None)
            
            if pid:
                # إذا كان التطبيق يعمل، قم بإغلاقه
                logger.info(f"EA Desktop is running (PID: {pid}). Terminating...")
                process = psutil.Process(pid)
                if process.is_running():
                    process.terminate()
                    process.wait(timeout=10)
                    logger.info(f"EA Desktop (PID: {pid}) terminated successfully.")
                else:
                    logger.warning(f"EA Desktop (PID: {pid}) is not running.")
                
                # إعادة تشغيل التطبيق بعد الإغلاق
                logger.info("Restarting EA Desktop after termination...")
                app_path = self.get_eadesktop_path()
                if app_path and os.path.exists(app_path):
                    os.startfile(app_path)
                    logger.info(f"EA Desktop started successfully from: {app_path}")
                else:
                    logger.error("Failed to find EA Desktop executable path for restarting.")
            else:
                # إذا لم يكن التطبيق يعمل، قم بتشغيله
                logger.info("EA Desktop is not running. Starting application...")
                app_path = self.get_eadesktop_path()
                if app_path and os.path.exists(app_path):
                    os.startfile(app_path)
                    logger.info(f"EA Desktop started successfully from: {app_path}")
                else:
                    logger.error("Failed to find EA Desktop executable path.")
        except Exception as e:
            logger.error(f"Error managing EA Desktop: {e}")


    def get_eadesktop_path(self):
        """الحصول على مسار EA Desktop من الريجستري"""
        try:
            reg_key_path = r"SOFTWARE\Electronic Arts\EA Desktop"
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_key_path)
            app_path, _ = winreg.QueryValueEx(reg_key, "DesktopAppPath")
            winreg.CloseKey(reg_key)
            return app_path
        except FileNotFoundError:
            logger.error("EA Desktop registry key not found.")
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
            2. Click the three-dot menu on the game's image.<br>
            3. Click on Repair.
            </p>
            """

            # إنشاء QLabel للتعليمات
            steps_label = QLabel(steps, self)
            steps_label.setStyleSheet("background-color: transparent;")  # جعل خلفية النص شفافة
            steps_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # محاذاة النص إلى الأعلى واليسار
            steps_label.setWordWrap(False)  # تعطيل تغليف النص

            # إضافة QLabel للتعليمات
            layout.addWidget(steps_label)

            # الرسالة الإضافية
            additional_message = QLabel(
                "It may take some time to repair, you can close this window.",
                self
            )
            additional_message.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 12px; background-color: transparent;")
            additional_message.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # محاذاة النص إلى الأعلى واليسار

            # إضافة الرسالة الإضافية إلى الحاوية
            layout.addWidget(additional_message)

            # إضافة الحاوية إلى التخطيط الرئيسي
            self.main_layout.addWidget(self.transparent_container)
        except Exception as e:
            self.handle_error(f"Error creating transparent container: {e}")


    # معالجة الأخطاء
    def handle_error(self, message):
        logger.error(message)  # تسجيل الخطأ
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)  # عرض رسالة الخطأ للمستخدم
# ----------------------------------- الدالة الرئيسية -----------------------------------
def main():
    try:
        # إنشاء تطبيق Qt
        app = QApplication(sys.argv)
        # تطبيق نمط QSS من ملف Styles.qss
        with importlib.resources.open_text('UIComponents', 'Styles.qss', encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        setTheme(Theme.DARK)  # تحديد السمة الداكنة
        setThemeColor("#00FF00")  # تحديد اللون الأخضر
        # إنشاء النافذة الرئيسية
        main_window = EAAppWindow()
        main_window.show()  # عرض النافذة
        # بدء التطبيق
        return app.exec()
    except Exception as e:
        logger.error(f"Error in main: {e}")  # تسجيل الخطأ
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Error", 0x10)  # عرض رسالة الخطأ

# تشغيل التطبيق
if __name__ == "__main__":
    main()
