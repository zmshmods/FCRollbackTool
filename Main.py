# --------------------------------------- Standard Libraries ---------------------------------------
import sys, os, ctypes, subprocess, webbrowser , requests
# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QMenu, QWidgetAction, QFrame, QWidget, QSpacerItem, QSizePolicy, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QSize, QPoint, QOperatingSystemVersion, QTimer, QSharedMemory, QPropertyAnimation
from PySide6.QtGui import QGuiApplication, QAction, QPixmap, QIcon, QPainter, QColor, QPixmap
from qframelesswindow import AcrylicWindow, StandardTitleBar
from qfluentwidgets import setTheme, setThemeColor, Theme, FluentIcon, CheckBox
# --------------------------------------- Project-Specific Imports ---------------------------------------
from UIWindows.SelectGameWindow import SelectGameWindow
from UIWindows.TitleUpdateTable import TableWidgetComponent
from UIWindows.DownloadWindow import DownloadWindow
from UIWindows.InstallWindow import InstallWindow
from UIComponents.Tooltips import apply_tooltip
from UIWindows.Messageboxes.DownloadDisclaimerMessagebox import MessageBoxManager
import Core.Initializer
from Core.Logger import logger
from UIComponents.AcrylicEffect import AcrylicEffect
from UIComponents.MenuBar import MenuBar
from Core.LaunchVanilla import launch_vanilla_threaded
from UIComponents.MainStyles import MainStyles
from Core.ToolUpdater import check_for_updates, UpdateWindow
class GameManager:
    def __init__(self):
        self.selected_game_path = ""
        self.game_content = None
        self.config_cache = None

    def load_game_data(self):
        try:
            if not self.config_cache:
                self.config_cache = Core.Initializer.Initializer.initialize_and_load_config()

            self.selected_game_path = self.config_cache.get("selected_game", "")
            if self.selected_game_path:
                self.game_content = Core.Initializer.Initializer.load_game_content(self.selected_game_path)
                return self.game_content.get("content_version", "(N/A Content Version)")
            else:
                self.game_content = None
                logger.warning("No game content loaded as no game was selected.")
                return "(N/A Content Version)"
        except Exception as e:
            self.game_content = None
            logger.exception(f"Error loading game data: {e}")
            return "(N/A Content Version)"

# -------------------------------------- مفتاح الاداة ------------------------------------------------

class Window(AcrylicWindow):
    def __init__(self, parent=None):
        self.config_cache = None
        super().__init__(parent=parent)
        self.download_windows = []
        self.game_manager = GameManager()
        self.content_version = self.game_manager.load_game_data()
        combined_version = f"{ToolVersion} {self.content_version}" 
        self.setWindowTitle(f"FC Rollback Tool - {combined_version}")
        self.resize(640, 400)
        AcrylicEffect(self)
        screen = QGuiApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        x = (screen.width() - window_geometry.width()) // 2
        y = (screen.height() - window_geometry.height()) // 2
        self.move(x, y)
        self.setup_ui()

    def update_config(self, key, value):
        try:
            if not self.config_cache:
                self.config_cache = Core.Initializer.Initializer.initialize_and_load_config()
            
            install_options = self.config_cache.get("install_options", {})
            install_options[key] = value
            self.config_cache["install_options"] = install_options
            Core.Initializer.Initializer.initialize_and_load_config(self.config_cache)
        except Exception as e:
            logger.exception(f"Error updating config: {e}")

    def create_title_bar(self):
        try:
            title_bar = StandardTitleBar(self)
            self.setTitleBar(title_bar)
            title_bar.setDoubleClickEnabled(False)
            title_bar.maxBtn.hide()

            # تخطيط شريط العنوان
            title_bar_layout = QHBoxLayout()
            title_bar_layout.setContentsMargins(5, 0, 5, 0)
            title_bar_layout.setSpacing(5)

            # أيقونة
            icon_label = QLabel(self)
            icon_pixmap = QPixmap("Data/Assets/Icons/FRICON.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(icon_pixmap)
            icon_label.setFixedSize(24, 24)
            icon_label.setStyleSheet("background-color: transparent;")
            icon_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            title_bar_layout.addWidget(icon_label)

            # نص العنوان
            title_label = QLabel(self.windowTitle(), self, styleSheet="color: white; background-color: transparent; font-size: 16px;", alignment=Qt.AlignVCenter | Qt.AlignLeft)
            title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)  # يعطي النص وزنًا
            title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            title_label.mousePressEvent = lambda event: setattr(self, '_drag_position', event.globalPos() - self.frameGeometry().topLeft()) if event.button() == Qt.LeftButton else None
            title_label.mouseMoveEvent = lambda event: self.move(event.globalPos() - getattr(self, '_drag_position', event.globalPos())) if event.buttons() == Qt.LeftButton else None
            title_bar_layout.addWidget(title_label)

            # زر "Launch"
            self.launch_button = QPushButton(" Launch Vanilla", self)
            self.launch_button.setFixedHeight(32)  # تحديد الارتفاع فقط
            self.launch_button.setCursor(Qt.PointingHandCursor)
            self.original_icon = QIcon("Data/Assets/Icons/ic_fluent_play_24_regular.png")
            self.success_icon = QIcon("Data/Assets/Icons/ic_fluent_checkmark_circle_24_filled.png")
            self.launch_button.setIcon(self.original_icon)
            self.launch_button.setIconSize(QSize(24, 24))
            self.launch_button.setStyleSheet(
                "QPushButton { background-color: transparent; border-radius: 0; border: 0; color: white; }"
                "QPushButton:hover { background-color: rgba(255, 255, 255, 20); }"
                "QPushButton:pressed { background-color: rgba(255, 255, 255, 15); }"
            )
            apply_tooltip(self.launch_button, "launch_vanilla_button")
            # ربط الزر بالحدث باستخدام lambda لاستدعاء دالة launch_vanilla_threaded
            self.launch_button.clicked.connect(
                lambda: [
                    self.launch_button.clicked.disconnect(),  # فصل الإشارة
                    self.AnimateLaunchVanillaButton(),
                    launch_vanilla_threaded(),
                    QTimer.singleShot(30000, lambda: self.launch_button.clicked.connect(
                        lambda: [self.AnimateLaunchVanillaButton(), launch_vanilla_threaded()]
                    ))  # إعادة الإشارة بعد 30 ثانية
                ]
            )

            title_bar_layout.addWidget(self.launch_button)

            # طول شريط العنوان
            spacer_item = QSpacerItem(0, 32, QSizePolicy.Minimum, QSizePolicy.Fixed)
            title_bar_layout.addItem(spacer_item)
            # إضافة Spacer صغير بعد الزر لخلق مسافة على اليمين
            small_spacer = QSpacerItem(87, 0, QSizePolicy.Minimum, QSizePolicy.Minimum)
            title_bar_layout.addItem(small_spacer)

            # تطبيق التخطيط
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.addLayout(title_bar_layout)
            self.main_layout.addWidget(QWidget(self, styleSheet="background-color: rgba(255, 255, 255, 0.1);", fixedHeight=1))

        except Exception as e:
            self.handle_error(f"Error creating title bar: {e}")

    def AnimateLaunchVanillaButton(self):
            # تغيير الأيقونة إلى success_icon
            self.launch_button.setIcon(self.success_icon)
            # إضافة تأثير التلاشي باستخدام الرسوم المتحركة للشفافية
            self.launch_button.setGraphicsEffect(None)  # إزالة أي تأثير سابق
            self.effect = QGraphicsOpacityEffect(self.launch_button)
            self.launch_button.setGraphicsEffect(self.effect)
            self.animation = QPropertyAnimation(self.effect, b"opacity")
            self.animation.setDuration(1200)  
            self.animation.setStartValue(1.0)
            self.animation.setEndValue(0.5)
            # عند انتهاء التلاشي الأول، أظهر الأيقونة الأصلية مع تأثير تدريجي
            def restore_icon():
                self.launch_button.setIcon(self.original_icon)
                self.animation.setStartValue(0.5)
                self.animation.setEndValue(1.0)
                self.animation.start()
            QTimer.singleShot(30000, restore_icon)
            # بدء التلاشي الأول
            self.animation.start()


    def setup_ui(self):
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 0)
            self.create_title_bar()
            self.main_layout.setSpacing(0)
            
            self.MenuBar = MenuBar(self)
            self.MenuBar.create_MenuBar()
            
            self.table_component = TableWidgetComponent(self, game_content=self.game_manager.game_content)
            self.main_layout.addWidget(self.table_component)

            self.create_buttons()
            self.update_buttons_based_on_row(self.table_component.table.selectionModel().currentIndex(), None)
            self.table_component.table.selectionModel().currentRowChanged.connect(self.update_buttons_based_on_row)
            
        except Exception as e:
            self.handle_error(f"Error setting up UI: {e}")

# --------------------------------------- تحديث حالة الأزرار حسب الصف المحدد ---------------------------------------
    # استمع لتغيير العنصر في الجدول
    def on_item_changed(self, item):
        if item.column() == 3:  # اذا تم تغيير العمود الذي يحتوي على الحالة
            current_index = self.table_component.table.currentIndex()  # استخدام currentIndex بدلاً من selectedIndexes
            if current_index.isValid():  # التأكد من أن الصف المحدد صالح
                self.update_buttons_based_on_row(current_index, None)

    # تعديل على الوظيفة الخاصة بتحديث الأزرار
    def update_buttons_based_on_row(self, current, previous):
        if current.row() >= 0:
            status_item = self.table_component.table.item(current.row(), 3)  # الحالة في العمود 3
            if status_item:
                status_text = status_item.text()
                self.download_button.setEnabled(status_text == "Available for Download")
                self.install_button.setEnabled(status_text == "Ready to Install (Stored in Profile)")
                self.install_options_button.setEnabled(status_text == "Ready to Install (Stored in Profile)")
        else:
            self.download_button.setEnabled(False)
            self.install_button.setEnabled(False)
            self.install_options_button.setEnabled(False)

            # ربط الحدث مع الجدول
            self.table_component.table.itemChanged.connect(self.on_item_changed)

# --------------------------------------- إنشاء الأزرار ---------------------------------------
    def create_buttons(self):
        try:
            # زر تغيير اللعبة
            self.change_game_button = QPushButton("")
            self.change_game_button.setIcon(FluentIcon.GAME.icon(Theme.DARK))
            self.change_game_button.clicked.connect(self.change_game)
            apply_tooltip(self.change_game_button, "change_game")

            # زر فتح المجلد
            self.open_profile_button = QPushButton("")
            self.open_profile_button.setIcon(FluentIcon.FOLDER.icon(Theme.DARK))
            self.open_profile_button.clicked.connect(self.open_profile_folder)
            apply_tooltip(self.open_profile_button, "open_profile_folder")

            # زر Install
            self.install_button = QPushButton(" Install")
            self.install_button.setIcon(FluentIcon.FOLDER_ADD.icon(Theme.DARK))
            self.install_button.clicked.connect(self.start_install)
            apply_tooltip(self.install_button, "install_button")
            self.install_button.setStyleSheet("border-top-right-radius: 0px; border-bottom-right-radius: 0px;")

            # زر Install Options
            self.install_options_button = QPushButton("")
            self.install_options_button.setIcon(FluentIcon.ARROW_DOWN.icon(Theme.DARK))
            self.install_options_button.setFlat(True)
            self.install_options_button.clicked.connect(self.show_install_options_menu)
            apply_tooltip(self.install_options_button, "install_options_button")
            self.install_options_button.setFixedSize(28, 28)
            self.install_options_button.setIconSize(QSize(12, 12))
            self.install_options_button.setStyleSheet("""
                QPushButton {
                    border-top-left-radius: 0px;
                    border-bottom-left-radius: 0px;
                    border-left: 1px solid rgba(255, 255, 255, 0.1);
                }
            """)

            # زر التنزيل
            self.download_button = QPushButton(" Download")
            self.download_button.setIcon(FluentIcon.DOWNLOAD.icon(Theme.DARK))
            self.download_button.clicked.connect(self.start_download)
            apply_tooltip(self.download_button, "download_button")

            # زر فتح الرابط في المتصفح
            self.open_url_button = QPushButton(" Open URL")
            self.open_url_button.setIcon(FluentIcon.LINK.icon(Theme.DARK))
            self.open_url_button.clicked.connect(self.open_in_browser)
            apply_tooltip(self.open_url_button, "open_url_button")

            # --------- تخطيط داخلي لأزرار Install و Options ---------
            install_arrow_layout = QHBoxLayout()
            install_arrow_layout.setContentsMargins(0, 0, 0, 0)
            install_arrow_layout.setSpacing(0)
            install_arrow_layout.addWidget(self.install_button)
            install_arrow_layout.addWidget(self.install_options_button)

            # --------- التخطيط العام للأزرار ---------
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(10, 0, 10, 0)
            button_layout.setSpacing(5)

            # إضافة الأزرار إلى التخطيط
            button_layout.addWidget(self.change_game_button)
            button_layout.addWidget(self.open_profile_button)
            button_layout.addStretch()
            button_layout.addLayout(install_arrow_layout)  # إضافة التخطيط الفرعي
            button_layout.addWidget(self.download_button)
            button_layout.addWidget(self.open_url_button)

            # --------- حاوية جديدة للأزرار ---------
            self.ButtonContainer = QWidget(self)
            self.ButtonContainer.setObjectName("ButtonContainer")  # تعيين اسم الحاوية
            self.ButtonContainer.setFixedHeight(45)  # تحديد ارتفاع الحاوية
            self.ButtonContainer.setLayout(button_layout)

            # إضافة الحاوية إلى التخطيط الرئيسي
            self.main_layout.addWidget(self.ButtonContainer)


        except Exception as e:
            self.handle_error(f"Error creating buttons: {e}")


# --------------------------------------- عرض قائمة خيارات التثبيت ---------------------------------------
    def show_install_options_menu(self):
        try:
            menu = QMenu(self)

            install_options = self.game_manager.config_cache.get("install_options", {})

            # تعريف الـ CheckBox الأول (إنشاء الباك اب)
            checkBox1 = CheckBox("Create backup folder before install", self)
            checkBox1.setTristate(False)
            checkBox1.setChecked(install_options.get("backup_checkbox", False))
            checkBox1.setStyleSheet("font-size: 12px; color: white;")  
            apply_tooltip(checkBox1, "backup_checkbox")

            checkBox_action1 = QWidgetAction(self)
            checkBox_action1.setDefaultWidget(checkBox1)
            menu.addAction(checkBox_action1)

            # تعريف الـ CheckBox الثاني (حذف التحديث من مجلد البروفايل)
            checkBox2 = CheckBox("Delete it from profile once installed", self)
            checkBox2.setTristate(False)
            checkBox2.setChecked(install_options.get("delete_stored_update_checkbox", False))
            checkBox2.setStyleSheet("font-size: 12px; color: white;")  
            apply_tooltip(checkBox2, "delete_stored_update_checkbox")

            checkBox_action2 = QWidgetAction(self)
            checkBox_action2.setDefaultWidget(checkBox2)
            menu.addAction(checkBox_action2)

            # ربط التغييرات مع ملف التكوين عند تغيير الحالات
            checkBox1.toggled.connect(lambda: self.update_config("backup_checkbox", checkBox1.isChecked()))
            checkBox2.toggled.connect(lambda: self.update_config("delete_stored_update_checkbox", checkBox2.isChecked()))

            button_pos = self.install_options_button.mapToGlobal(QPoint(0, self.install_options_button.height()))
            menu.exec(button_pos)
        except Exception as e:
            self.handle_error(f"Error showing install options menu: {e}")  # خطأ في عرض قائمة خيارات التثبيت

# ----------------------------------- تثبيت التحديث -----------------------------------

    def start_install(self):
        """الدالة التي يتم استدعاؤها عند الضغط على زر Install."""
        try:
            selected_game_path = self.game_manager.selected_game_path
            update_name = self.get_selected_update_name()

            if not update_name:
                self.handle_error("No update selected for installation.")  # لم يتم اختيار تحديث للتثبيت
                return
            # التحقق من أن نافذة التثبيت ليست مفتوحة
            if not hasattr(self, 'install_window') or self.install_window is None or not self.install_window.isVisible():
                self.install_window = InstallWindow(selected_game_path, update_name, table_component=self.table_component)
                self.install_window.setWindowModality(Qt.ApplicationModal)  # جعل النافذة طاغية
                self.install_window.show()  # عرض نافذة التثبيت
            else:
                # تشغيل الصوت الافتراضي للنظام (تنبيه)
                self.install_window.raise_()  # إذا كانت النافذة مفتوحة بالفعل، اجعلها في المقدمة
                self.install_window.activateWindow()  # تفعيل النافذة إذا كانت مفتوحة بالفعل
        except Exception as e:
            self.handle_error(f"Error starting installation: {e}")  # خطأ أثناء بدء التثبيت

# ----------------------------------- استرجاع اسم التحديث المحدد -----------------------------------
    def get_selected_update_name(self):
        selected_row = self.table_component.table.selectedIndexes()
        if selected_row:
            return self.table_component.table.item(selected_row[0].row(), 0).text()
        return None

# ----------------------------------- بدء التحميل -----------------------------------
    def start_download(self):
        """فتح نافذة تحميل بناءً على الصف المحدد."""
        try:
            config = self.game_manager.config_cache if self.game_manager.config_cache else Core.Initializer.Initializer.initialize_and_load_config()
            show_message_boxes = config.get("Show_Message_Boxes", {})
            download_disclaimer = show_message_boxes.get("download_disclaimer", True)  # القيمة الافتراضية هي True

            if download_disclaimer:
                if not MessageBoxManager(self).show_message_box():
                    return  # العودة دون بدء التنزيل

                selected_row = self.table_component.table.currentRow()
                updates_list = self.table_component.game_content.get("fc24tu-updates", []) or self.table_component.game_content.get("fc25tu-updates", []) or self.table_component.game_content.get("xxtu-updates", [])

                if selected_row < 0 or selected_row >= len(updates_list):
                    MessageBoxManager(self).show_message_box()  # عرض رسالة الخطأ في حال لم يتم اختيار صف صالح
                    return

                update_info = updates_list[selected_row]
                update_name, download_url = update_info.get("name", "Unknown Update"), update_info.get("download_url")

                if not download_url:
                    logger.error("Download URL is missing for the selected update.")  # رابط التنزيل مفقود للتحديث المحدد
                    MessageBoxManager(self).show_message_box()  # عرض رسالة التحذير في حال عدم وجود رابط
                    return

                short_game_name = next((key.split("tu-")[0].upper() for key in self.table_component.game_content if "tu-updates" in key), "UnknownGame")

                logger.info(f"Starting download: {update_name} | URL: {download_url}")  # بدء التنزيل: {update_name} | URL: {download_url}

                show_message_boxes["download_disclaimer"] = False
                config["Show_Message_Boxes"] = show_message_boxes
                Core.Initializer.Initializer.initialize_and_load_config(config)

                download_window = DownloadWindow(update_name, download_url, short_game_name)
                self.download_windows.append(download_window)
                download_window.show()
            else:
                # إذا كانت الرسالة التحذيرية غير مفعلة (False)، نقوم مباشرة ببدء التنزيل
                selected_row = self.table_component.table.currentRow()
                updates_list = self.table_component.game_content.get("fc24tu-updates", []) or self.table_component.game_content.get("fc25tu-updates", []) or self.table_component.game_content.get("xxtu-updates", [])

                if selected_row < 0 or selected_row >= len(updates_list):
                    MessageBoxManager(self).show_message_box()  # عرض رسالة الخطأ في حال لم يتم اختيار صف صالح
                    return

                update_info = updates_list[selected_row]
                update_name, download_url = update_info.get("name", "Unknown Update"), update_info.get("download_url")

                if not download_url:
                    logger.error("Download URL is missing for the selected update.")  # رابط التنزيل مفقود للتحديث المحدد
                    MessageBoxManager(self).show_message_box()  # عرض رسالة التحذير في حال عدم وجود رابط
                    return

                short_game_name = next((key.split("tu-")[0].upper() for key in self.table_component.game_content if "tu-updates" in key), "UnknownGame")

                logger.info(f"Starting download: {update_name} | URL: {download_url}")  # بدء التنزيل: {update_name} | URL: {download_url}

                download_window = DownloadWindow(update_name, download_url, short_game_name)
                self.download_windows.append(download_window)
                download_window.show()
        except Exception as e:
            logger.error(f"Error starting download: {e}")  # خطأ في بدء التنزيل

# ----------------------------------- فتح الرابط في المتصفح -----------------------------------
    def open_in_browser(self):
        """فتح رابط التحديث في المتصفح."""
        try:
            selected_row = self.table_component.table.currentRow()
            updates_list = self.table_component.game_content.get("fc24tu-updates", []) or self.table_component.game_content.get("fc25tu-updates", [])

            if selected_row >= 0 and selected_row < len(updates_list):
                download_url = updates_list[selected_row].get("download_url")
                if download_url:
                    webbrowser.open(download_url)
        except Exception as e:
            logger.error(f"Error opening URL in browser: {e}")  # خطأ في فتح الرابط في المتصفح

# ----------------------------------- فتح مجلد البروفايل -----------------------------------
    def open_profile_folder(self):
        """فتح مجلد Profiles الخاص باللعبة المحددة."""
        try:
            if not self.game_manager.selected_game_path:
                self.handle_error("No game selected. Please select a game first.")  # لم يتم اختيار لعبة، من فضلك اختر لعبة أولاً

            short_game_name = os.path.basename(self.game_manager.selected_game_path.strip("\\/")).replace("EA SPORTS ", "").replace(" ", "")
            profiles_directory = os.path.join(os.getcwd(), "Profiles", short_game_name)

            if os.path.exists(profiles_directory):
                os.startfile(profiles_directory)  # فتح المجلد باستخدام النظام
            else:
                self.handle_error(f"Profile folder not found for the game: {short_game_name}")  # لم يتم العثور على مجلد البروفايل للعبة: {short_game_name}
        except Exception as e:
            self.handle_error(f"Error opening profile folder: {e}")  # خطأ في فتح مجلد البروفايل

# ----------------------------------- تغيير اللعبة -----------------------------------
    def change_game(self):
        """تغيير اللعبة وإعادة تشغيل التطبيق."""
        try:
            Core.Initializer.Initializer.reset_selected_game()
            
            executable_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FC Rollback Tool.exe")
            
            if os.path.exists(executable_path):
                subprocess.Popen([executable_path] + sys.argv)
            else:
                subprocess.Popen([sys.executable, "main.py"] + sys.argv)
            
            self.close()
        except Exception as e:
            self.handle_error(f"Error while restarting the application: {e}")  # خطأ أثناء إعادة تشغيل التطبيق
# ----------------------------------- معالجة الأخطاء -----------------------------------
    def handle_error(self, message):
        """معالجة الأخطاء."""
        logger.error(message)
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)
# ----------------------------------- الدالة الرئيسية -----------------------------------
from Core.ToolUpdater import ToolVersion, check_for_updates, UpdateWindow, should_show_update
from ctypes import windll
def main():
    try:
        app = QApplication(sys.argv)
        app.setWindowIcon(QIcon("Data/Assets/Icons/FRICON.ico"))
        shared_memory = QSharedMemory("FCRollbackToolSharedMemory")

        if not shared_memory.create(1):
            ctypes.windll.user32.MessageBoxW(0, "FC Rollback Tool is already running.", "Error", 0x10)
            sys.exit()

        app.setStyleSheet(MainStyles())
        setTheme(Theme.DARK)
        setThemeColor("#00FF00")

        # تحميل الإعدادات
        config = Core.Initializer.Initializer.initialize_and_load_config()

        if Core.Initializer.Initializer.validate_and_update_crc(config.get("selected_game", "")):
            # إذا تم التحقق بنجاح من CRC، عرض النافذة الرئيسية
            main_window = Window()
            main_window.show()
        else:
            # إذا لم يكن هناك لعبة مختارة، عرض نافذة اختيار اللعبة
            Core.Initializer.Initializer.reset_selected_game()
            select_game_window = SelectGameWindow()
            select_game_window.gameSelected.connect(
                lambda game_path: Core.Initializer.Initializer.initialize_and_load_config({"selected_game": game_path})
            )
            select_game_window.show()

        # استدعاء الدالة قبل الخروج لتنظيف الملفات المؤقتة
        app.aboutToQuit.connect(lambda: Core.Initializer.Initializer.create_temp_folder(clean=True))

        # التحقق من التحديثات
        if should_show_update():  # إذا كان يجب عرض نافذة التحديث
            latest_version = check_for_updates()
            if latest_version:
                logger.info(f"New tool version available: {latest_version}")  # تتبع

                # عرض نافذة التحديث
                def show_update_window():
                    windll.user32.MessageBeep(0xFFFFFFFF)  # إصدار صوت التنبيه الافتراضي للنظام
                    update_window = UpdateWindow(new_version=latest_version)
                    update_window.setWindowModality(Qt.ApplicationModal)  # جعل النافذة إجبارية
                    update_window.show()

                QTimer.singleShot(1000, show_update_window)  # عرض فوري لنافذة التحديث

        # تشغيل التطبيق
        sys.exit(app.exec())

    except Exception as e:
        logger.error(f"Application error: {e}")
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Error", 0x10)

if __name__ == "__main__":
    main()
