# --------------------------------------- Standard Libraries ---------------------------------------
import sys, importlib.resources, ctypes, psutil, os, json, subprocess
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

# ----------------------------------- مدير اللعبة -----------------------------------
class GameManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.selected_game_path = ""
        self.config_cache = None

    def load_game_data(self):
        """تحميل بيانات اللعبة المختارة من ملف التكوين."""
        try:
            # تحميل بيانات التكوين
            self.config_cache = self.load_config()

            # استخراج المسار الخاص باللعبة المختارة
            self.selected_game_path = self.config_cache.get("selected_game", "")
            if not self.selected_game_path:
                logger.error("No selected game path found in config.")
                return None, None

            # استخراج اسم اللعبة القصير
            short_game_name = os.path.basename(self.selected_game_path.strip("\\/")).replace("EA SPORTS ", "").replace(" ", "")

            # تحديد معرف Steam للعبة
            SteamAppID = {
                "FC24": 2195250,
                "FC25": 2669320
            }

            # البحث عن معرف اللعبة
            if short_game_name in SteamAppID:
                unique_number = SteamAppID[short_game_name]
                return short_game_name, unique_number
            else:
                logger.error(f"Game '{short_game_name}' is not recognized.")
                return None, None
        except Exception as e:
            logger.error(f"Error loading game data: {e}")
            return None, None

    def load_config(self):
        """تحميل ملف التكوين."""
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            return config_data
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            return {}

# ----------------------------------- نافذة تشغيل ستيم -----------------------------------
class SteamWindow(AcrylicWindow):
    # إعدادات النافذة
    def __init__(self, parent=None):
        self.config_cache = None
        super().__init__(parent=parent)
        self.setWindowTitle("Repair Game - Steam")  # تعيين عنوان النافذة
        self.resize(370, 100)  # تحديد حجم النافذة
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)  # تثبيت النافذة أعلى النوافذ الأخرى
        AcrylicEffect(self)  # تفعيل أو تعطيل تأثير الأكريليك بناءً على نوع الويندوز
        self.center_window()  # ضبط موقع النافذة في وسط الشاشة
        self.manage_steam_game()  # استدعاء المنطق أثناء إنشاء النافذة
        self.setup_ui()  # إعداد واجهة المستخدم

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

    def setup_ui(self):
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 5)
            self.create_title_bar()  # إنشاء شريط العنوان
            self.create_transparent_container()  # إنشاء الحاوية الشفافة مع التعليمات
            self.main_layout.setSpacing(0)
        except Exception as e:
            self.handle_error(f"Error setting up UI: {e}")

    def manage_steam_game(self):
        """إدارة تشغيل إصلاح اللعبة في Steam"""
        try:
            game_manager = GameManager(config_file="config.json")
            selected_game, unique_number = game_manager.load_game_data()

            if not selected_game or not unique_number:
                logger.error("No valid game selected for repair.")
                return

            # حفظ اسم اللعبة لتستخدمه في دالة create_transparent_container
            self.selected_game = selected_game

            # تشغيل ستيم مع أمر الإصلاح
            command = f"steam://validate/{unique_number}"
            os.system(f"start {command}")
            logger.info(f"Steam launched with repair command for game: {selected_game} (AppID: {unique_number})")
        except Exception as e:
            logger.error(f"Error managing Steam game: {e}")


    def create_transparent_container(self):
        try:
            # إنشاء الحاوية الشفافة
            self.transparent_container = QWidget(self)
            self.transparent_container.setStyleSheet("background-color: rgba(0, 0, 0, 0.1);")  # تحديد اللون الشفاف
            self.transparent_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # جعل الحاوية قابلة للتوسيع
            layout = QVBoxLayout(self.transparent_container)  # إعداد تخطيط للحاوية الشفافة
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)  # محاذاة النصوص إلى الأعلى واليسار

            # إنشاء تخطيط أفقي للسطر الأول
            first_row_layout = QHBoxLayout()
            first_row_layout.setAlignment(Qt.AlignLeft)

            # إضافة الأيقونة
            icon_label = QLabel(self)
            pixmap = QPixmap("Assets/Icons/ic_fluent_checkmark_circle_24_regular.png")
            pixmap.isNull()
            icon_label.setPixmap(pixmap)
            icon_label.setStyleSheet("background-color: transparent;")  # جعل خلفية الأيقونة شفافة
            icon_label.setFixedSize(20, 20)  # ضبط حجم الأيقونة
            icon_label.setScaledContents(True)  # السماح بتغيير حجم الصورة حسب الحاوية

            # إضافة النص بجانب الأيقونة
            text_label = QLabel(f"Steam launched with repair command for ({getattr(self, 'selected_game', 'Unknown')})", self)
            text_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background-color: transparent;")
            text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # محاذاة النص إلى اليسار والوسط رأسيًا

            # إضافة الأيقونة والنص إلى التخطيط الأفقي
            first_row_layout.addWidget(icon_label)
            first_row_layout.addWidget(text_label)

            # إضافة التخطيط الأفقي إلى التخطيط الرئيسي
            layout.addLayout(first_row_layout)

            # إنشاء تخطيط أفقي للسطر الثاني
            second_row_layout = QHBoxLayout()
            second_row_layout.setAlignment(Qt.AlignLeft)

            # إضافة "أيقونة وهمية" فارغة
            empty_icon = QLabel(self)
            empty_icon.setFixedSize(20, 20)  # نفس حجم الأيقونة السابقة
            empty_icon.setStyleSheet("background-color: transparent;")  # جعل الخلفية شفافة

            # إضافة النص بجانب "الأيقونة الوهمية"
            additional_text = QLabel(
                "It may take some time to repair, you can close this window.",
                self
            )
            additional_text.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 12px; background-color: transparent;")
            additional_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # محاذاة النص إلى اليسار والوسط رأسيًا

            # إضافة "الأيقونة الوهمية" والنص إلى التخطيط الأفقي
            second_row_layout.addWidget(empty_icon)
            second_row_layout.addWidget(additional_text)

            # إضافة التخطيط الأفقي للسطر الثاني إلى التخطيط الرئيسي
            layout.addLayout(second_row_layout)

            # إضافة الحاوية إلى التخطيط الرئيسي
            self.main_layout.addWidget(self.transparent_container)
        except Exception as e:
            self.handle_error(f"Error creating transparent container: {e}")



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
        main_window = SteamWindow()
        main_window.show()  # عرض النافذة
        # بدء التطبيق
        return app.exec()
    except Exception as e:
        logger.error(f"Error in main: {e}")  # تسجيل الخطأ
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Error", 0x10)  # عرض رسالة الخطأ

# تشغيل التطبيق
if __name__ == "__main__":
    main()
