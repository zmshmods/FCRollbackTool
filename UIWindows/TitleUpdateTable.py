# --------------------------------------- Standard Libraries ---------------------------------------
import os
import ctypes
# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtWidgets import QVBoxLayout, QHeaderView, QFrame, QTableWidgetItem, QAbstractItemView
from PySide6.QtCore import Qt, QFileSystemWatcher, Signal
from qfluentwidgets import TableWidget
# --------------------------------------- Project-specific Imports ---------------------------------------
import Core.Initializer
from Core.Logger import logger

class TableWidgetComponent(QFrame):
    table_updated_signal = Signal()
    def __init__(self, parent=None, game_content=None):
        super().__init__(parent)
        self.game_content = game_content

        # تحديد مسار مجلدات البروفايل للـ FC24 و FC25
        self.profiles_fc24_directory = os.path.join(os.getcwd(), "Profiles", "FC24", "TitleUpdates")
        self.profiles_fc25_directory = os.path.join(os.getcwd(), "Profiles", "FC25", "TitleUpdates")

        # إعداد التخطيط الرئيسي للإطار
        self.layout = QVBoxLayout(self)
        self.setStyleSheet("background-color: transparent;")
        self.layout.setContentsMargins(0, 0, 0, 0)  # تباعد داخلي
        self.layout.setSpacing(0)

        # إنشاء الجدول باستخدام TableWidget
        self.table = TableWidget(self)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(0)
        self.table.setWordWrap(False)
        self.table.setColumnCount(4)  # عدد الأعمدة
        self.table.setHorizontalHeaderLabels(["Name", "Size", "Released Date", "Status"])
        
        self.layout.addWidget(self.table)

        # إعداد البيانات الأولية
        self.populate_table()

        # إعداد الرأس
        header = self.table.horizontalHeader()

        header.setSectionResizeMode(QHeaderView.ResizeToContents)  # تمديد تلقائي للأعمدة
        header.setStretchLastSection(True)  # تمديد العمود الأخير
        header.setSectionResizeMode(QHeaderView.ResizeToContents)  # تمديد الأعمدة حسب المحتوى
        # السماح بتغيير حجم الأعمدة يدويًا
        header.setSectionResizeMode(QHeaderView.Interactive)  # تمكين تغيير الحجم من قبل المستخدم
        header.setStretchLastSection(True)  # تمديد العمود الأخير
        header.setFixedHeight(32)


        # تحسين المظهر
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().hide()
        # السماح بتحديد صف واحد فقط
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # استخدام QFileSystemWatcher لمراقبة التغييرات في المجلدات
        self.watcher = QFileSystemWatcher(self)
        self.watcher.addPath(self.profiles_fc24_directory)
        self.watcher.addPath(self.profiles_fc25_directory)
        self.watcher.directoryChanged.connect(self.update_table)

    def handle_error(self, message):
        """
        عرض الأخطاء في نافذة منبثقة مع تسجيلها في اللوق.
        """
        logger.error(message)  # تسجيل الخطأ في اللوق
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)  # عرض مربع رسالة
    #تحديث الجدول + حتى يتم تحديث الحالات
    def update_table(self, path=None):
        try:
            self.populate_table()  # تحديث الجدول عند اكتشاف تغيير
            logger.info("TU Table Updated")
        except Exception as e:
            self.handle_error(f"Error occurred while updating table: {str(e)}")

    def populate_table(self):
        """
        تعبئة الجدول بالتحديثات.
        """
        try:
            # دمج التحديثات من FC25 و FC24 (بدون دمج الملفات)
            updates = self.game_content.get("fc25tu-updates", []) + self.game_content.get("fc24tu-updates", []) if self.game_content else []
            current_crc = Core.Initializer.Initializer.initialize_and_load_config().get("crc")

            self.table.setRowCount(len(updates))

            # استخراج اسم اللعبة المحددة
            selected_game_path = Core.Initializer.Initializer.initialize_and_load_config().get("selected_game", "")
            short_game_name = os.path.basename(selected_game_path.strip("\\/")).replace("EA SPORTS ", "").replace(" ", "")

            # التحقق من وجود الملفات في المجلدين
            profile_files_fc24 = set(os.listdir(self.profiles_fc24_directory)) if os.path.exists(self.profiles_fc24_directory) else set()
            profile_files_fc25 = set(os.listdir(self.profiles_fc25_directory)) if os.path.exists(self.profiles_fc25_directory) else set()
            # قائمة بالامتدادات المضغوطة المدعومة
            supported_compressed_extensions = [".rar", ".7z", ".zip"]

            for i, update in enumerate(updates):
                # إعداد الأعمدة
                name_item = QTableWidgetItem(update.get("name", "N/A"))
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 0, name_item)

                size_item = QTableWidgetItem(update.get("size", "N/A"))
                size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 1, size_item)

                date_item = QTableWidgetItem(update.get("released_date", "N/A"))
                date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 2, date_item)

                # إعداد الحالة الخاصة بالتحديث
                status_item = QTableWidgetItem()
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)

                # حالة "Installed (Current)" إذا كان الـ CRC متطابقًا
                if update.get("crc") == current_crc:
                    status_item.setText("Installed (Current)")
                    status_item.setForeground(Qt.green)  # اللون الأخضر
                else:
                    # إزالة المسافات الزائدة وتحويل الأسماء إلى حروف صغيرة
                    update_name = update.get("name", "").strip().lower()

                    # استخدام الاسم بالكامل (بما في ذلك الامتداد) بدون تقسيمه
                    update_name_base = update_name

                    # التأكد من أن جميع الملفات في المجلدات تم تحويلها إلى حروف صغيرة وإزالة المسافات
                    profile_files_fc24 = [file.strip().lower() for file in profile_files_fc24]
                    profile_files_fc25 = [file.strip().lower() for file in profile_files_fc25]

                    # التحقق من تطابق الاسم مع الملفات في مجلد FC24 بشكل دقيق
                    found_fc24 = any(update_name_base == file for file in profile_files_fc24)
                    # التحقق من تطابق الاسم مع الملفات في مجلد FC25 بشكل دقيق
                    found_fc25 = any(update_name_base == file for file in profile_files_fc25)

                    # إضافة منطق لتحليل الملفات المضغوطة (مثل .rar, .7z, .zip)
                    found_fc24_compressed = any(update_name_base == os.path.splitext(file)[0] for file in profile_files_fc24 if os.path.splitext(file)[1] in supported_compressed_extensions)
                    found_fc25_compressed = any(update_name_base == os.path.splitext(file)[0] for file in profile_files_fc25 if os.path.splitext(file)[1] in supported_compressed_extensions)

                    # إذا تم العثور على الملف المضغوط أو المجلد العادي
                    if found_fc24 or found_fc25 or found_fc24_compressed or found_fc25_compressed:
                        status_item.setText("Ready to Install (Stored in Profile)")
                        status_item.setForeground(Qt.yellow)  # اللون الأصفر
                    else:
                        # حالة "Not stored" الحالة الديفولت
                        status_item.setText("Available for Download")
                        status_item.setForeground(Qt.lightGray)  # اللون الباهت (رمادي فاتح)

                self.table.setItem(i, 3, status_item)

        except Exception as e:
            self.handle_error(f"Error occurred while populating table: {str(e)}")