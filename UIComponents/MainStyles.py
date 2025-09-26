def MainStyles():
    return """
    /*######## Title Bar ########*/
    StandardTitleBar { background-color: transparent; border: none; }
    StandardTitleBar > QLabel { color: white; background-color: transparent; padding-left: 5px; }

    MinimizeButton { 
        qproperty-normalColor: white; 
        qproperty-normalBackgroundColor: transparent; 
        qproperty-hoverColor: white; 
        qproperty-hoverBackgroundColor: rgba(255, 255, 255, 20); 
        qproperty-pressedColor: white; 
        qproperty-pressedBackgroundColor: rgba(255, 255, 255, 15); 
    }

    MaximizeButton { 
        qproperty-normalColor: white; 
        qproperty-normalBackgroundColor: transparent; 
        qproperty-hoverColor: white; 
        qproperty-hoverBackgroundColor: rgba(255, 255, 255, 20); 
        qproperty-pressedColor: white; 
        qproperty-pressedBackgroundColor: rgba(255, 255, 255, 15); 
    }

    CloseButton { 
        qproperty-normalColor: white; 
        qproperty-normalBackgroundColor: transparent; 
        qproperty-hoverBackgroundColor: #b12a1e; 
        qproperty-pressedBackgroundColor: #a5271c; 
    }

    /*######## Buttons ########*/
    QPushButton { 
        background-color: rgba(255, 255, 255, 0.1); 
        color: white; 
        padding: 5px; 
        border: 1px solid rgba(255, 255, 255, 0.1); 
        border-radius: 5px; 
    }
    QPushButton:hover { background-color: rgba(255, 255, 255, 0.2); }
    QPushButton:pressed { background-color: rgba(255, 255, 255, 0.3); }
    QPushButton:disabled { 
        background-color: rgba(255, 255, 255, 0.04); 
        color: rgba(255, 255, 255, 0.6); 
    }

    QWidget#ButtonContainer { background-color: transparent; }

    /*######## Menu ########*/
    QMenu { 
        background-color: rgb(43, 43, 43); 
        border-radius: 5px; 
    }

    CheckBox { 
        font-size: 12px; 
        padding: 5px; 
        background-color: transparent; 
        border-radius: 5px;
    }

    CheckBox:hover { 
        background-color: rgb(60, 60, 60); 
        border-radius: 5px; 
    }

    CheckBox::indicator { 
        width: 16px; 
        height: 16px; 
        background-color: transparent; 
        border-radius: 5px;
    }

    CheckBox::indicator:hover { 
        background-color: rgb(60, 60, 60); 
        border-radius: 5px; 
    }

    CheckBox::indicator:pressed { 
        background-color: rgb(55, 55, 55); 
        border-radius: 5px; 
    }
    """
