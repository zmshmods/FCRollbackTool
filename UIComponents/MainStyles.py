# MainStyles.py

def MainStyles():
    return """
    /* شريط العنوان */
    StandardTitleBar {
        background-color: transparent; /* خلفية شفافة */
        border: none;
    }

    StandardTitleBar > QLabel {
        color: white;
        background-color: transparent; /* تأكد من أن النص في شريط العنوان شفاف */
        padding-left: 5px; /* إضافة مسافة بين النص وحافة النافذة */
    }

    /* زر عام */
    QPushButton {
        background-color: rgba(255, 255, 255, 0.1); /* شفاف جدًا */
        color: white;
        padding: 5px;
        border: 1px solid rgba(255, 255, 255, 0.1); /* حدود شفافة */
        border-radius: 5px; /* زوايا مستديرة */
    }

    QPushButton:hover {
        background-color: rgba(255, 255, 255, 0.2); /* يزيد الشفافية عند التمرير */
    }

    QPushButton:pressed {
        background-color: rgba(255, 255, 255, 0.3); /* لون أكثر وضوحًا عند الضغط */
    }

    QPushButton:disabled {
        background-color: rgba(255, 255, 255, 0.04);
        color:rgba(255, 255, 255, 0.6);
    }

    /* MinimizeButton style */
    MinimizeButton {
        qproperty-normalColor: white;
        qproperty-normalBackgroundColor: transparent;
        qproperty-hoverColor: white;
        qproperty-hoverBackgroundColor: rgba(255, 255, 255, 20);
        qproperty-pressedColor: white;
        qproperty-pressedBackgroundColor: rgba(255, 255, 255, 15);
    }

    /* MaximizeButton style */
    MaximizeButton {
        qproperty-normalColor: white;
        qproperty-normalBackgroundColor: transparent;
        qproperty-hoverColor: white;
        qproperty-hoverBackgroundColor: rgba(255, 255, 255, 20);
        qproperty-pressedColor: white;
        qproperty-pressedBackgroundColor: rgba(255, 255, 255, 15);
    }

    /* CloseButton style */
    CloseButton {
        qproperty-normalColor: white;
        qproperty-normalBackgroundColor: transparent;
        qproperty-hoverBackgroundColor: #b12a1e;
        qproperty-pressedBackgroundColor: #a5271c;
    }

    /* Menu styling */
    QMenu {
        background-color:rgb(43, 43, 43);  /* لون الخلفية */
        border-radius: 5px;
    }

    /* CheckBox styling */
    CheckBox {
        font-size: 12px;  /* تقليص حجم الخط داخل الـ CheckBox */
        padding: 5px;  /* تقليص padding لتقليص المساحة حول النص */
        background-color: transparent;  /* جعل الخلفية شفافة */
    }

    /* الخلفية الخاصة بالسطر*/ 
    CheckBox:hover {
        background-color:rgb(60, 60, 60);  /* لون الهوفر */
        border-radius: 5px;
    }

    /* تخصيص المربع داخل الـ CheckBox */
    CheckBox::indicator {
        width: 16px;  /* عرض المربع */
        height: 16px; /* ارتفاع المربع */
        background-color: transparent;  /* خلفية شفافة للمربع */
    }

    /* تأثير hover على المربع فقط */
    CheckBox::indicator:hover {
        background-color:rgb(60, 60, 60);  /* لون الهوفر */
        border-radius: 5px;
    }

    /* تأثير الضغط على المربع فقط */
    CheckBox::indicator:pressed {
        background-color:rgb(55, 55, 55);  /* لون البريسيد */
        border-radius: 5px;
    }
    QWidget#ButtonContainer {
        background-color: transparent;
    }
    """
