# --------------------------------------- Standard Libraries ---------------------------------------
import os
import ctypes
# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtWidgets import QApplication, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QHeaderView, QTableWidgetItem, QFileSystemModel, QStackedLayout, QWidget, QAbstractItemView
from PySide6.QtCore import Qt, QSize, Signal, QThread, QObject, QTimer
from PySide6.QtGui import QGuiApplication
from qframelesswindow import AcrylicWindow, StandardTitleBar
from qfluentwidgets import TableWidget, setTheme, setThemeColor, Theme
# --------------------------------------- Project-specific Imports ---------------------------------------
import Core.Initializer
from Core.Logger import logger
from UIComponents.Spinner import LoadingSpinner
from UIComponents.Tooltips import apply_tooltip
from UIComponents.AcrylicEffect import AcrylicEffect

class SelectGameWindow(AcrylicWindow):
    gameSelected = Signal(str)

    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.setWindowTitle("FC Rollback Tool - Select Game")
            self.resize(500, 300)
            AcrylicEffect(self)  # إستدعاء .. تعطيل / تفعيل الاكريلك حسب انوع الويندوز 
            # تمركز النافذة
            screen = QGuiApplication.primaryScreen().geometry()
            window_geometry = self.geometry()
            x = (screen.width() - window_geometry.width()) // 2
            y = (screen.height() - window_geometry.height()) // 2
            self.move(x, y)

            self.setup_ui()
        except Exception as e:
            self.handle_error(f"Error initializing SelectGameWindow: {e}")

        
    def setup_ui(self):
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 5, 0, 5)

            self.create_title_bar()
            self.stacked_layout = QStackedLayout()
            self.create_table()
            self.create_spinner()
            self.stacked_layout.setCurrentWidget(self.table)
            self.main_layout.addLayout(self.stacked_layout)
            self.create_buttons()
        except Exception as e:
            self.handle_error(f"Error setting up UI: {e}")

    def create_title_bar(self):
        try:
            title_bar_layout = QVBoxLayout()
            title_bar_layout.setContentsMargins(0, 3, 0, 3)
            # تخصيص شريط العنوان
            title_bar = StandardTitleBar(self)
            self.setTitleBar(title_bar)
            # إخفاء أزرار التكبير والتصغير
            title_bar.maxBtn.hide()  # إخفاء زر التكبير
            title_bar.minBtn.hide() # إخفاء زر التصغير
            title_bar.setDoubleClickEnabled(False)  # تعطيل التكبير بالنقر المزدوج
            title_label = QLabel("FC Rollback Tool - Select Game")
            title_label.setStyleSheet("color: white; background-color: transparent; font-size: 16px; padding-left: 5px;")
            title_label.setAlignment(Qt.AlignLeft)
            title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            title_bar_layout.addWidget(title_label)
            self.main_layout.addLayout(title_bar_layout)
        except Exception as e:
            self.handle_error(f"Error creating title bar: {e}")

    def create_table(self):
        try:
            self.table = TableWidget(self)
            self.table.setBorderVisible(True)
            self.table.setBorderRadius(2)
            self.table.setWordWrap(False)
            self.table.setIconSize(QSize(32, 32))
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["Name", "Path"])
            self.table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeToContents)
            header.setStretchLastSection(True)
            QTimer.singleShot(0, lambda: header.setSectionResizeMode(QHeaderView.Interactive))
            self.table.setAlternatingRowColors(False)
            self.table.verticalHeader().hide()
            # ربط النقر المزدوج بدالة handle_select_button
            self.table.itemDoubleClicked.connect(lambda _: self.handle_select_button())
            self.stacked_layout.addWidget(self.table)
            self.populate_table()
        except Exception as e:
            self.handle_error(f"Error creating table: {e}")

    def create_spinner(self):
        try:
            self.spinner_container = QWidget(self)
            layout = QVBoxLayout(self.spinner_container)
            layout.setAlignment(Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)

            self.spinner_container.setStyleSheet("background-color: transparent;")

            self.spinner_widget = LoadingSpinner(self)
            self.spinner_widget.setStyleSheet("background-color: transparent;")
            layout.addWidget(self.spinner_widget, alignment=Qt.AlignCenter)

            self.status_label = QLabel("Initializing...", self)
            self.status_label.setStyleSheet(
                "color: white; font-size: 14px; background-color: transparent;")
            self.status_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.status_label, alignment=Qt.AlignCenter)

            self.stacked_layout.addWidget(self.spinner_container)
        except Exception as e:
            self.handle_error(f"Error creating spinner: {e}")
            
    def create_buttons(self):
        try:
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(10, 10, 10, 10)

            # زر Select
            self.select_button = QPushButton("Select")
            self.select_button.setFixedSize(80, 30)
            self.select_button.clicked.connect(self.handle_select_button)
            apply_tooltip(self.select_button, "select_button")  # تطبيق التلميح لزر Select

            # زر Rescan
            self.rescan_button = QPushButton("Rescan")
            self.rescan_button.setFixedSize(80, 30)
            self.rescan_button.clicked.connect(self.handle_rescan)
            apply_tooltip(self.rescan_button, "rescan_button")  # تطبيق التلميح لزر Rescan

            # نص "Game Not Found?" (بدون QLabel، فقط تلميح)
            self.clickable_label = QLabel("Game Not Found?", self)
            apply_tooltip(self.clickable_label, "game_not_found")
            self.clickable_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 0.7); /* لون أبيض باهت */
                    background-color: transparent; /* إزالة الخلفية */
                    font-size: 12px;
                    text-decoration: none;
                }
                QLabel:hover {
                    color: white; /* لون أبيض للهوفير */
                }
            """)
            self.clickable_label.setCursor(Qt.PointingHandCursor)
            # إضافة العناصر إلى التخطيط
            button_layout.addWidget(self.clickable_label, alignment=Qt.AlignLeft)  # النص
            button_layout.addStretch()  # إضافة مسافة
            button_layout.addWidget(self.rescan_button)
            button_layout.addWidget(self.select_button)

            self.main_layout.addLayout(button_layout)
        except Exception as e:
            self.handle_error(f"Error creating buttons: {e}")


    def populate_table(self):
        try:
            games = Core.Initializer.Initializer.get_games_from_registry()
            self.table.setRowCount(len(games))
            model = QFileSystemModel()
            model.setRootPath("")
            for row, (exe_name, exe_path) in enumerate(games.items()):
                folder_name = os.path.basename(os.path.dirname(exe_path))
                folder_path = os.path.dirname(exe_path)

                # إعداد العنصر الخاص بالاسم
                item_name = QTableWidgetItem(folder_name)
                item_name.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                item_name.setIcon(model.fileIcon(model.index(exe_path)))
                item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)  # تعطيل التحرير
                self.table.setItem(row, 0, item_name)

                # إعداد العنصر الخاص بالمسار
                item_path = QTableWidgetItem(folder_path)
                item_path.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                item_path.setFlags(item_path.flags() & ~Qt.ItemIsEditable)  # تعطيل التحرير
                self.table.setItem(row, 1, item_path)
        except Exception as e:
            self.handle_error(f"Error populating table: {e}")


    def handle_rescan(self):
        try:
            self.show_spinner()
            self.update_status_label("Scanning for games...")
            QTimer.singleShot(100, self.perform_rescan)
        except Exception as e:
            self.handle_error(f"Error during rescan: {e}")

    def perform_rescan(self):
        try:
            self.update_status_label("Retrieving game paths...")
            self.populate_table()
        finally:
            self.show_table()
            self.update_status_label("")
            
    def handle_select_button(self):
        try:
            current_row = self.table.currentRow()
            if current_row >= 0:
                selected_path = self.table.item(current_row, 1).text()

                self.show_spinner()
                self.update_status_label("Loading game configuration...")

                # إخفاء الأزرار أثناء تشغيل العملية
                for button in self.findChildren(QPushButton):
                    button.hide()

                # إنشاء الخيط والعامل
                self.thread = QThread()
                self.worker = GameProcessingWorker(selected_path)
                self.worker.moveToThread(self.thread)

                # ربط الإشارات
                self.thread.started.connect(self.worker.run)
                
                # عرض حالة التقدم خلال العمليات المختلفة
                self.worker.update_status.connect(lambda msg: QTimer.singleShot(0, lambda: self.update_status_label(msg)))
                
                self.worker.finished.connect(self.thread.quit)  # إيقاف الخيط بعد الانتهاء
                self.worker.finished.connect(self.worker.deleteLater)
                self.thread.finished.connect(self.thread.deleteLater)

                # نجاح العملية
                self.worker.success.connect(self.open_main_window)
                
                # التعامل مع الأخطاء
                self.worker.error.connect(self.handle_error)

                # بدء الخيط
                self.thread.start()
        except Exception as e:
            self.handle_error(f"Error handling select button: {e}")


    def open_main_window(self):
        from Main import Window
        self.main_window = Window()
        self.main_window.show()
        self.close()

    def update_status_label(self, message):
        if not QApplication.instance().thread() == QThread.currentThread():
            QTimer.singleShot(0, lambda: self.status_label.setText(message))  # تحديث في الخيط الرئيسي
        else:
            self.status_label.setText(message)

    def show_spinner(self):
        QTimer.singleShot(0, lambda: self.stacked_layout.setCurrentWidget(self.spinner_container))

    def show_table(self):
        QTimer.singleShot(0, lambda: self.stacked_layout.setCurrentWidget(self.table))

    def handle_error(self, message):
        logger.error(message)
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)


class GameProcessingWorker(QObject):
    finished = Signal()
    error = Signal(str)
    success = Signal()
    update_status = Signal(str)

    def __init__(self, selected_path):
        super().__init__()
        self.selected_path = selected_path

    def run(self):
        try:
            self.update_status.emit("Loading configuration...")
            Core.Initializer.Initializer.initialize_and_load_config({"selected_game": self.selected_path})

            self.update_status.emit("Validating game and checking CRC...")
            if Core.Initializer.Initializer.validate_and_update_crc(self.selected_path):
                logger.info("Game validated and CRC checked successfully.")
                self.update_status.emit("Loading game content...")
                Core.Initializer.Initializer.load_game_content(self.selected_path)
                self.success.emit()
            else:
                self.error.emit("Failed to validate the game.")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

def main():
    try:
        app = QApplication([])
        setTheme(Theme.DARK)
        setThemeColor("#00FF00")
        select_game_window = SelectGameWindow()
        select_game_window.show()
        app.exec()
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, f"Application error: {e}", "Error", 0x10)


if __name__ == "__main__":
    main()
