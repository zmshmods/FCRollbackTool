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
# ----------------------------------- مفتاح الاداة -----------------------------------
class InformationWindow(AcrylicWindow):
    # إعدادات النافذة
    def __init__(self, parent=None):
        self.config_cache = None
        super().__init__(parent=parent)
        self.setWindowTitle("Information")  # تعيين عنوان النافذة
        self.resize(640, 400)
        AcrylicEffect(self)  # تفعيل أو تعطيل تأثير الأكريليك بناءً على نوع الويندوز
        self.setup_ui()  # إعداد واجهة المستخدم
    # وظيفة لضبط موقع النافذة في وسط الشاشة
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
            icon_pixmap = QPixmap("Data/Assets/Icons/ic_fluent_info_24_outlined.png")  # تحميل الأيقونة
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

    # إعداد واجهة المستخدم
    def setup_ui(self):
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 5)
            self.create_title_bar()  # إنشاء شريط العنوان
            self.create_transparent_container()  # إنشاء الحاوية الشفافة
            self.main_layout.setSpacing(0)
        except Exception as e:
            self.handle_error(f"Error setting up UI: {e}")

    def create_transparent_container(self):
        try:
            self.transparent_container = QWidget(self)
            self.transparent_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.transparent_container.setStyleSheet("background-color: rgba(0, 0, 0, 0.1);")
            layout = QVBoxLayout(self.transparent_container)
            layout.setAlignment(Qt.AlignLeft)

            def create_link_section(title, links):
                section_layout = QVBoxLayout()
                section_label = QLabel(f"<b>{title}:</b>")
                section_label.setStyleSheet("color: white; font-size: 14px; background-color: transparent;")
                section_layout.addWidget(section_label)

                for text, url in links:
                    link_layout = QHBoxLayout()

                    # Add the icon
                    icon_label = QLabel()
                    pixmap = QPixmap("Data/Assets/Icons/ic_fluent_link_24_regular.png").scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    icon_label.setPixmap(pixmap)
                    icon_label.setFixedSize(16, 16)
                    icon_label.setStyleSheet("background-color: transparent;")

                    # Add the text link
                    link_label = QLabel(f"<a href='{url}' style='color: rgba(255, 255, 255, 0.8); text-decoration: none;'>{text}</a>")
                    link_label.setStyleSheet("color: white; font-size: 14px; background-color: transparent;")
                    link_label.setOpenExternalLinks(True)

                    # Combine the icon and text in one layout
                    link_layout.addWidget(icon_label)
                    link_layout.addWidget(link_label)
                    link_layout.addStretch()

                    section_layout.addLayout(link_layout)

                return section_layout

            # About Section
            about_label = QLabel(
                "<b>About FC Rollback Tool:</b><br>"
                "<a style='color: rgba(255, 255, 255, 0.8);'>A simple tool for managing updates of EA Sports FC games and restoring previous versions.</a>"
            )
            about_label.setStyleSheet("color: white; font-size: 14px; background-color: transparent;")
            about_label.setWordWrap(True) 
            layout.addWidget(about_label)

            layout.addWidget(self._create_separator())

            # Libraries/Services/Tools Used Section
            libraries_links = [
                ("PyQt-Fluent-Widgets", "https://github.com/zhiyiYo/PyQt-Fluent-Widgets"),
                ("MediaFire", "https://www.mediafire.com"),
                ("Aria2", "https://github.com/aria2/aria2"),
                ("UnRAR", "https://www.rarlab.com/rar_add.htm"),
                ("7-Zip", "https://7-zip.org/download.html"),
            ]
            layout.addLayout(create_link_section("Libraries/Services/Tools Used", libraries_links))

            layout.addWidget(self._create_separator())

            # UsefulLinks Section
            useful_links = [
                ("Patreon: ZMSH Mods", "https://www.patreon.com/zmsh"),
                ("Github: FC Rollback Tool", "https://github.com/ZMSHMods/FCRollbackTool"),
                ("Discord: EA FC Modding World", "https://discord.com/invite/fifa-modding-world-fmw-1000239960672182272"),
            ]
            layout.addLayout(create_link_section("Useful Links", useful_links))

            layout.addWidget(self._create_separator())

            # Footer
            footer_label = QLabel("Version 1.0 Beta - Maintained by zmshactov")
            footer_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px; background-color: transparent;")
            footer_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(footer_label)

            self.main_layout.addWidget(self.transparent_container)
        
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
        main_window = InformationWindow()
        main_window.show()  # عرض النافذة
        # بدء التطبيق
        return app.exec()
    except Exception as e:
        logger.error(f"Error in main: {e}")  # تسجيل الخطأ
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Error", 0x10)  # عرض رسالة الخطأ

# تشغيل التطبيق
if __name__ == "__main__":
    main()
