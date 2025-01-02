# --------------------------------------- Standard Libraries ---------------------------------------
import json
import os
import warnings
# --------------------------------------- Third-Party Libraries ---------------------------------------
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ToolTipPosition
from qfluentwidgets.components.material import AcrylicToolTipFilter # need full qfluentwidgets
warnings.filterwarnings("ignore", category=UserWarning)

def get_current_game_name():
    config_file = "config.json"  # مسار ملف الإعدادات
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as file:
                config = json.load(file)
                selected_game = config.get("selected_game", "None")
                if selected_game and selected_game != "None":
                    return f'<span style="color: #02f102;">{selected_game.split("\\")[-1]}</span>'
                else:
                    return '<span style="color: #02f102;">None</span>'
        except Exception as e:
            print(f"Error reading config.json: {e}")
            return '<span style="color: #02f102;">None</span>'
    return '<span style="color: #02f102;">None</span>'

# قاموس التولتيب
TOOLTIPS = {
    "game_not_found": {
        "text": lambda: 'Make sure to run your game at least once so the tool can detect it.',
        "position": ToolTipPosition.TOP,
        "delay": 200
    },
    "change_game": {
        "text": lambda: f'Current Game: {get_current_game_name()}<br>Click to change your game.',
        "position": ToolTipPosition.TOP,
        "delay": 880
    },
    "select_button": {
        "text": "Load game configuration",
        "position": ToolTipPosition.TOP,
        "delay": 880
    },
    "rescan_button": {
        "text": "Rescan to detect games again",
        "position": ToolTipPosition.TOP,
        "delay": 880
    },
    "skip_button": {
        "text": "Skip loading configuration and go to the main window",
        "position": ToolTipPosition.TOP,
        "delay": 880
    },
    "download_button": {
        "text": "Download the selected update",
        "position": ToolTipPosition.TOP,
        "delay": 880
    },
    "open_url_button": {
        "text": "Open download URL in browser",
        "position": ToolTipPosition.TOP,
        "delay": 880
    },
    "open_profile_folder": {
        "text": "Open game profile folder",
        "position": ToolTipPosition.TOP,
        "delay": 880
    },
    "install_button": {
        "text": "Auto Install the selected update",
        "position": ToolTipPosition.BOTTOM_LEFT,
        "delay": 880
    },
    "install_options_button": {
        "text": "Installation Options",
        "position": ToolTipPosition.BOTTOM_LEFT,  
        "delay": 880
    },
    "backup_checkbox": {
        "text": "A backup folder will be created in \"Profiles\" folder for the current update before installing the new one.",
        "position": ToolTipPosition.TOP_LEFT, 
        "delay": 880
    },
    "delete_stored_update_checkbox": {
        "text": "Delete the stored update from \"Profiles\" folder after it has been installed to your game.",
        "position": ToolTipPosition.BOTTOM_LEFT,
        "delay": 880
    },
    "launch_vanilla_button": {
        "text": "Launch the game with zero mods/tools to ensure its activation/stability before rollback.",
        "position": ToolTipPosition.BOTTOM_LEFT,
        "delay": 880
    }
}

# دالة لتحديد مكان التولتيب بناءً على المساحة المتاحة
def get_optimal_tooltip_position(widget: QWidget, identifier: str) -> ToolTipPosition:
    """تحديد أفضل موضع للتولتيب بناءً على المساحة المتاحة حول العنصر."""
    tooltip_data = TOOLTIPS.get(identifier)
    # إذا كان العنصر هو install_options_button، استخدم موقع BOTTOM_RIGHT
    if identifier == "install_options_button":
        return ToolTipPosition.BOTTOM_LEFT
    if identifier == "backup_checkbox":
        return ToolTipPosition.TOP_LEFT
    if identifier == "delete_stored_update_checkbox":
        return ToolTipPosition.BOTTOM_LEFT
    if identifier == "launch_vanilla_button":
        return ToolTipPosition.BOTTOM_LEFT
    # إذا لم يكن العنصر هو install_options_button، فضع التولتيب في الأعلى
    return ToolTipPosition.TOP

# دالة لتطبيق التولتيب على العنصر
def apply_tooltip(widget: QWidget, identifier: str):
    """
    تطبيق تلميح أكريليكي لأي عنصر باستخدام معرف محدد.

    Args:
        widget (QWidget): عنصر واجهة المستخدم (زر أو عنصر آخر) الذي سيتم تطبيق التلميح عليه.
        identifier (str): معرف التلميح في قاموس TOOLTIPS.
    """
    tooltip_data = TOOLTIPS.get(identifier)
    if tooltip_data:
        # إذا كان النص دالة (مثل lambda)، يتم استدعاؤها للحصول على النص
        text = tooltip_data["text"]() if callable(tooltip_data["text"]) else tooltip_data["text"]
        widget.setToolTip(text)  # تعيين النص
        # تحديد الموقع الأمثل للتولتيب بناءً على المعرف
        optimal_position = get_optimal_tooltip_position(widget, identifier)
        widget.installEventFilter(AcrylicToolTipFilter(
            widget,
            tooltip_data.get("delay", 880),  # التأخير قبل ظهور التلميح
            optimal_position  # الموقع الأمثل
        ))
    else:
        raise ValueError(f"Tooltip identifier '{identifier}' not found in TOOLTIPS.")
