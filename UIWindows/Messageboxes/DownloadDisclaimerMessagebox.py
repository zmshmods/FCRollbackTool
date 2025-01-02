# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtGui import QColor
from qfluentwidgets import MessageBoxBase, SubtitleLabel, CaptionLabel

# تخزين الرسائل في معجم واحد
MESSAGES = {
    "download_disclaimer": {
        "title": "Download Disclaimer",
        "message": (
            "Downloading a large number of files in a short period of time may result in your IP address being temporarily or permanently banned "
            "from MediaFire servers. "
            "You can also use the (Open URL) button to manually download the files if you prefer.\n\n"
            "Do you want to proceed?"
        )
    }
}


class MessageBoxManager(MessageBoxBase):
    """ مدير نافذة الرسائل المخصصة """

    def __init__(self, parent=None):
        super().__init__(parent)

        # استخدام الرسائل من القاموس
        message_data = MESSAGES["download_disclaimer"]

        self.titleLabel = SubtitleLabel(message_data["title"], self)
        self.messageLabel = CaptionLabel(message_data["message"])
        self.messageLabel.setWordWrap(True)  # التأكد من التفاف النص إذا كان طويلًا
        
        # تعيين لون النص إلى الأبيض
        self.messageLabel.setTextColor("#FFFFFF", QColor(255, 255, 255))

        # إضافة العناصر إلى واجهة العرض
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.messageLabel)

        # إضافة Checkbox إلى الرسالة
        #self.checkbox = CheckBox("Do not show this message again", self)
        #self.checkbox.setStyleSheet("color: white;")
        #self.viewLayout.addWidget(self.checkbox)

        # تغيير النصوص في الأزرار
        self.yesButton.setText('OK')
        self.cancelButton.setText('Cancel')

        self.widget.setMinimumWidth(350)

        # تطبيق corner radius على الأزرار والنوافذ
        self.applyStyle()

    def applyStyle(self):
        self.widget.setStyleSheet("""
            QWidget {
                border-radius: 5px;
            }
            QPushButton {
                border-radius: 5px; /* زوايا مستديرة */
            }
        """)

    def validate(self):
        """ لا حاجة هنا لأننا لا نحتاج للتحقق من صحة المدخلات. """
        return True

    def set_message(self, message_key):
        """ إعداد الرسالة والعنوان بناءً على المفتاح """
        message_data = MESSAGES.get(message_key, MESSAGES["download_disclaimer"])
        self.titleLabel.setText(message_data["title"])
        self.messageLabel.setText(message_data["message"])

    def show_message_box(self):
        """ طريقة لعرض رسالة المستخدم في حوار """
        return self.exec()