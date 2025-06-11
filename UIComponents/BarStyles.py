# UIComponents/BarStyles.py

def BarStyles():
    return """
    /* Disable focus rectangle for widgets in BarStyles scope */
    QPushButton:focus {
        outline: none;
        border: none;
    }
    QTabBar:focus {
        outline: none;
    }
    QMenu:focus {
        outline: none;
    }

    QPushButton {
        border-radius: 0px;
        border: none;
        background-color: transparent;
        color: white;
        font-size: 12px;
        font-weight: 600;
    }

    QPushButton:hover {
        background-color: rgba(255, 255, 255, 0.02);
        border-left: 1px solid rgba(255, 255, 255, 0.1);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }

    QPushButton:pressed {
        background-color: rgba(255, 255, 255, 0.04);
    }

    QMenu {
        background-color: #2c2c2c;
        border-radius: 0px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin: 0px;
        padding: 0px;
    }

    QMenu::item {
        padding: 5px 15px;
        text-align: left;
        color: white;
        margin: 2px 0px;
    }

    QMenu::icon {
        margin: 10px;
    }

    QMenu::item:selected {
        background-color: #353535;
        border-radius: 0px;
    }

    QMenu::item:pressed {
        background-color: #303030;
        border-radius: 0px;
    }

    QMenu::separator {
        height: 1px;
        background-color: rgba(255, 255, 255, 0.1);
        margin: 0px 0px 0px 0px;
    }

    QMenu::item:disabled {
        color: rgba(255, 255, 255, 0.3);
        background-color: transparent;
        border: none;
    }

    QMenu::item:disabled QMenu::icon {
        color: rgba(255, 255, 255, 0.3);
    }

    QMenu::right-arrow {
        height: 12px;
        width: 12px;
        margin: 0px;
    }

    QTabWidget::pane {
        border: 0;
        background-color: transparent;
    }

    QTabBar {
        background-color: transparent;
    }

    QTabBar::tab {
        background-color: transparent;
        color: white;
        font-size: 12px;
        font-weight: 600;
        padding: 5px 10px;
        border-left: 1px solid rgba(255, 255, 255, 0.05);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }

    QTabBar::tab:hover {
        background-color: rgba(255, 255, 255, 0.02);
    }

    QTabBar::tab:selected {
        background-color: rgba(255, 255, 255, 0.04);
        /*border-bottom: 1px solid rgba(255, 255, 255, 0.01);*/
    }
    """