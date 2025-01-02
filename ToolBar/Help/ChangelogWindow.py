# --------------------------------------- Standard Libraries ---------------------------------------
import sys, importlib.resources, ctypes
# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import setTheme, setThemeColor, Theme
from qframelesswindow import AcrylicWindow, StandardTitleBar
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtCore import Qt
# --------------------------------------- Project-Specific Imports ---------------------------------------
from UIComponents.AcrylicEffect import AcrylicEffect
from UIComponents.Tooltips import apply_tooltip
from Core.Logger import logger
from UIComponents.MainStyles import MainStyles
import requests
from Core.ToolUpdater import ToolVersion, ChangelogBaseURL

# ----------------------------------- مفتاح الاداة -----------------------------------
class ChangelogWindow(AcrylicWindow):
    def __init__(self, parent=None):
        self.config_cache = None
        super().__init__(parent=parent)
        self.setWindowTitle("Changelog")  # تعيين عنوان النافذة
        self.resize(640, 400)
        AcrylicEffect(self)  # تفعيل أو تعطيل تأثير الأكريليك بناءً على نوع الويندوز
        self.setup_ui()  # إعداد واجهة المستخدم
        # ضبط موقع النافذة في وسط الشاشة
        screen = QGuiApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        x = (screen.width() - window_geometry.width()) // 2
        y = (screen.height() - window_geometry.height()) // 2
        self.move(x, y)

    def create_title_bar(self):
        try:
            # استخدام StandardTitleBar كما هو
            title_bar = StandardTitleBar(self)
            self.setTitleBar(title_bar)
            # إخفاء أزرار التكبير
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
            # **إضافة الأيقونة إلى شريط العنوان**
            icon_label = QLabel(self)
            icon_pixmap = QPixmap("Assets/Icons/ic_fluent_code_24_filled.png")  # تحميل الأيقونة
            # ضبط حجم الأيقونة
            icon_pixmap = icon_pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(icon_pixmap)
            icon_label.setFixedSize(24, 24)  # تحديد حجم الأيقونة
            icon_label.setStyleSheet("background-color: transparent;")  # تعيين خلفية شفافة
            icon_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            # إضافة الأيقونة إلى التخطيط
            title_bar_layout.addWidget(icon_label)
            # إنشاء عنوان النافذة
            self.title_label = QLabel(self.windowTitle(), self)
            self.title_label.setStyleSheet("color: white; background-color: transparent; font-size: 16px;")
            self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)  # محاذاة العنوان يسار ووسط رأسيًا
            self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            # إضافة العنوان إلى التخطيط
            title_bar_layout.addWidget(self.title_label)
            self.main_layout.setContentsMargins(0, 0, 0, 0)  # إزالة الهوامش من التخطيط الرئيسي
            self.main_layout.addWidget(self.title_bar_container)
            # إضافة خط فاصل تحت شريط العنوان
            separator = QWidget(self)
            separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
            separator.setFixedHeight(1)
            self.main_layout.addWidget(separator)
        except Exception as e:
            self.handle_error(f"Error creating title bar: {e}")

    def setup_ui(self):
        """إعداد واجهة المستخدم."""
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 5)
            self.create_title_bar()  # إنشاء شريط العنوان
            self.create_transparent_container()  # إنشاء الحاوية الشفافة
            self.main_layout.setSpacing(0)
        except Exception as e:
            self.handle_error(f"Error setting up UI: {e}")

    def create_transparent_container(self):
        """إنشاء الحاوية الشفافة لعرض المحتوى وجلب ملف التغييرات."""
        try:
            # إذا كانت الحاوية موجودة مسبقًا، نظفها
            if hasattr(self, "transparent_container") and self.transparent_container.layout():
                layout = self.transparent_container.layout()
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            else:
                # إنشاء الحاوية إذا لم تكن موجودة
                self.transparent_container = QWidget(self)
                self.transparent_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.transparent_container.setStyleSheet("background-color: rgba(0, 0, 0, 0.1);")
                layout = QVBoxLayout(self.transparent_container)
                layout.setAlignment(Qt.AlignTop)  # جعل المحتوى يلتصق بالأعلى
                self.main_layout.addWidget(self.transparent_container)

            # محاولة تحميل وعرض ملف التغييرات
            try:
                # تكوين رابط ملف التغييرات
                changelog_url = f"{ChangelogBaseURL}{ToolVersion}.txt"
                response = requests.get(changelog_url, timeout=10)
                response.raise_for_status()

                # عنوان رقم النسخة
                version_label = QLabel(f"<b>FC Rollback Tool {ToolVersion}:</b>", self)
                version_label.setStyleSheet("font-size: 16px; color: white; background-color: transparent;")
                version_label.setAlignment(Qt.AlignLeft)
                layout.addWidget(version_label)

                # معالجة النصوص
                lines = response.text.splitlines()
                formatted_lines = [f"\u2022 {line.lstrip('-').strip()}" for line in lines if line.strip()]

                # عرض النصوص في الحاوية الشفافة
                for line in formatted_lines:
                    label = QLabel(line, self)
                    label.setStyleSheet("font-size: 16px; color: white; background-color: transparent;")
                    label.setAlignment(Qt.AlignLeft)
                    layout.addWidget(label)
            except Exception as e:
                # إذا حدث خطأ، عرض رسالة
                error_label = QLabel("Unable to fetch changelog.", self)
                error_label.setStyleSheet("font-size: 14px; color: red; background-color: transparent;")
                error_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(error_label)
                logger.error(f"Error fetching changelog: {e}")
        except Exception as e:
            self.handle_error(f"Error creating transparent container: {e}")

    def _create_separator(self):
        separator = QWidget(self)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.05);")
        separator.setFixedHeight(1)
        return separator

    # معالجة الأخطاء
    def handle_error(self, message):
        logger.error(message)  # تسجيل الخطأ
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)  # عرض رسالة الخطأ للمستخدم
# ----------------------------------- الدالة الرئيسية -----------------------------------
def main():
    try:
        # إنشاء تطبيق Qt
        app = QApplication(sys.argv)
        app.setStyleSheet(MainStyles())
        setTheme(Theme.DARK)  # تحديد السمة الداكنة
        setThemeColor("#00FF00")  # تحديد اللون الأخضر
        # إنشاء النافذة الرئيسية
        main_window = ChangelogWindow()
        main_window.show()  # عرض النافذة
        # بدء التطبيق
        return app.exec()
    except Exception as e:
        logger.error(f"Error in main: {e}")  # تسجيل الخطأ
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Error", 0x10)  # عرض رسالة الخطأ

# تشغيل التطبيق
if __name__ == "__main__":
    main()
