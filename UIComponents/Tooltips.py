import logging, os
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ToolTipPosition, ToolTipFilter
#from qfluentwidgets.components.material import AcrylicToolTipFilter
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager

# Color constants
COLORS = {
    "red": "#FF0000",
    "yellow": "#FFFF00",
    "green": "#00FF00"
}

# Formatting styles
STYLES = {
    "highlight": {"color": COLORS["green"]},
    "bold": {"font-weight": "bold"},
    "italic": {"font-style": "italic"},
    "underline": {"text-decoration": "underline"}
}

class TooltipFormatter:
    """Class to handle tooltip text formatting."""
    @staticmethod
    def format_text(text, formats=None):
        """
        Format text by applying styles to specified parts.
        Args:
            text (str): The raw text to format.
            formats (dict): Dictionary mapping text substrings to their styles.
                            Style can be either a list of styles or a dict of CSS properties.
        Returns:
            str: Formatted HTML text.
        """
        if not formats:
            return text.replace("\n", "<br>")
        
        formatted_text = text.replace("\n", "<br>")
        for target, style in formats.items():
            if isinstance(style, list):
                style_dict = {}
                for style_name in style:
                    style_dict.update(STYLES.get(style_name, {})) 
            elif isinstance(style, str):
                style_dict = STYLES.get(style, {})
            elif isinstance(style, dict):
                style_dict = style.copy()  # Use provided style dict
                if "color" in style_dict and style_dict["color"] in COLORS:
                    style_dict["color"] = COLORS[style_dict["color"]]
            else:
                style_dict = {}

            style_str = "; ".join([f"{k}: {v}" for k, v in style_dict.items()])
            formatted_text = formatted_text.replace(
                target, f'<span style="{style_str};">{target}</span>'
            )
        return formatted_text

def apply_tooltip(widget: QWidget, identifier: str):
    tooltip_data = TOOLTIPS.get(identifier)
    if not tooltip_data:
        logging.warning(f'Tooltip identifier "{identifier}" not found in TOOLTIPS. Skipping tooltip application.')
        return 
    
    text = tooltip_data["text"]() if callable(tooltip_data["text"]) else tooltip_data["text"]
    formats = tooltip_data["formats"]() if callable(tooltip_data.get("formats")) else tooltip_data.get("formats", {})

    formatted_text = TooltipFormatter.format_text(text, formats)
    
    widget.setToolTip(formatted_text)
    widget.installEventFilter(ToolTipFilter(
        widget,
        tooltip_data.get("delay", 880),
        tooltip_data.get("position", ToolTipPosition.TOP)
    ))

config_mgr = ConfigManager()

TOOLTIPS = {
    # Common
    "Placeholder": {"text": "", "position": ToolTipPosition.TOP, "delay": 0},
    "saveTypeOptions": {"text": "Choose the output format for the fetched files.", "position": ToolTipPosition.BOTTOM, "delay": 600},
    "browseButton": {"text": "Browse to select a directory for saving files.", "position": ToolTipPosition.BOTTOM, "delay": 600},

    # Main & Select Game Window
    "game_not_found": {"text": "Make sure to run your game at least once so the tool can detect it.", "position": ToolTipPosition.TOP, "delay": 200},
    "settings_button": {"text": "Settings", "position": ToolTipPosition.TOP, "delay": 880},

    "change_game": {"text": lambda: (gm := GameManager(), path := config_mgr.getConfigKeySelectedGame(), profile := gm._get_profile(path) if path else None, name := profile.display_name if profile else (os.path.basename(path) if path else 'None'), f"Current Game: {name}\nClick to change your game.")[-1], 
                    "formats": lambda: (gm := GameManager(), path := config_mgr.getConfigKeySelectedGame(), profile := gm._get_profile(path) if path else None, name := profile.display_name if profile else (os.path.basename(path) if path else 'None'), {name: ["highlight"]})[-1], 
                    "position": ToolTipPosition.TOP, "delay": 880},

    "rescan_button": {"text": "Rescan to detect games again", "position": ToolTipPosition.TOP, "delay": 880},
    "download_button": {"text": "Download the selected update", "position": ToolTipPosition.TOP, "delay": 880},
    "download_options_button": {"text": "Download Options", "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "open_url_button": {"text": "Open download URL in browser", "position": ToolTipPosition.TOP, "delay": 880},
    "open_profile_folder": {"text": "Open game profile folder", "position": ToolTipPosition.TOP, "delay": 880},
    "unistall_squad_button": {"text": "Unistall squads file", "position": ToolTipPosition.TOP, "delay": 880},
    "install_button": {"text": "Auto Install the selected update", "position": ToolTipPosition.TOP, "delay": 880},
    "install_options_button": {"text": "Installation Options", "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "launch_game_button": {"text": "Launch the game", "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "patch_notes_button": {"text": "Read the patch notes of the selected title update.", "position": ToolTipPosition.TOP, "delay": 880},
    "open_patch_notes_url_button": {"text": "Open the patch notes URL in browser.", "position": ToolTipPosition.TOP, "delay": 880},
    "fetch_tables_button": {"text": "Fetch the DB tables for the selected squad update.", "position": ToolTipPosition.TOP, "delay": 880},
    "fetch_changelogs_button": {"text": "Fetch the changelogs for the selected squad update.", "position": ToolTipPosition.TOP, "delay": 880},

    # SettingsWindow
    "ResetAllToDefault": {"text": "Reset all settings for all tabs to their default values.", "position": ToolTipPosition.BOTTOM, "delay": 600},
    "backupSettingsGameFolder": {"text": "This automatically backs up your game's settings folder before installing any title update or squads file.\nThis ensures you can restore your settings and save files for your game if something goes wrong.", 
                                 "formats": {"This ensures you can restore your settings and save files for your game if something goes wrong.": ["highlight"]}, 
                                 "position": ToolTipPosition.TOP_LEFT, "delay": 880},
    "backupCurrentTU": {"text": "A backup folder will be created in the Profiles folder for the current title update before installing the new one.\nThis allows you to quickly restore the title update if needed.", 
                        "formats": {"This allows you to quickly restore the title update if needed.": ["highlight"]}, 
                        "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "deleteTUAfterInatall": {"text": "This automatically deletes the title update archive from the Profiles folder after it has been installed on your game.\nThis helps save disk space and prevents the buildup of title update archives in Profiles folder.", 
                             "formats": {"This helps save disk space and prevents the buildup of title update archives in Profiles folder.": ["highlight"]}, 
                             "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "deleteSquadsAfterInatall": {"text": "This automatically deletes the squad update file from the Profiles folder after it has been installed on your game.\nThis helps save disk space and prevents the buildup of squad update files in Profiles folder.", 
                                 "formats": {"This helps save disk space and prevents the buildup of squad update files in Profiles folder.": ["highlight"]}, 
                                 "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "deleteLiveTuningUpdate": {"text": "This automatically deletes the Live Tuning Update file (attribdb.bin) after rolling back your title update.\nThis helps eliminate any changes to gameplay attributes, keeping the game using the original gameplay data from the title update only.", 
                               "formats": {"This helps eliminate any changes to gameplay attributes, keeping the game using the original gameplay data from the title update only.": ["highlight"]}, 
                               "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "deleteLiveTuningNow": {"text": "Delete Live Tuning Update", "position": ToolTipPosition.TOP, "delay": 880},
    "openLiveTuningFolder": {"text": "Locate", "position": ToolTipPosition.TOP, "delay": 880},

    # Download Options
    "segmentsOptions": {"text": "Sets the number of segments to split the download into.\nMore segments can increase download speed by enabling parallel downloads, but too many may cause instability or errors.", 
                        "formats": {"More segments can increase download speed by enabling parallel downloads, but too many may cause instability or errors.": ["highlight"]}, 
                        "position": ToolTipPosition.TOP_LEFT, "delay": 880},
    "speedLimitOptions": {"text": "This caps your download speed to a chosen value in KBytes/sec.\nThis helps manage bandwidth usage.", 
                          "formats": {"This helps manage bandwidth usage.": ["highlight"]}, 
                          "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "autoUseIDM": {"text": "This uses your installed Internet Download Manager (IDM) to handle downloads automatically.\nThis will override aria2.", 
                   "formats": {"This will override aria2.": ["highlight"]}, 
                   "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "changeIDMPath": {"text": "Change Internet Download Manager executable path.\nThis will override the automatically detected path.", 
                      "formats": {"This will override the automatically detected path.": ["highlight"]}, 
                      "position": ToolTipPosition.BOTTOM_LEFT, "delay": 880},
    "redetectIDMPath": {"text": "Re-Detect Internet Download Manager executable path.", "position": ToolTipPosition.TOP, "delay": 880},
    
    # Tables Settings
    "resetAllTablesSettings": {"text": "Reset all table settings to default values.", "position": ToolTipPosition.TOP, "delay": 880},
    "columnOrderOptions": {"text": "AsRead: Maintains the exact order of columns as read from the DB file. \"This is how FET exports tables\"\nBitOffset: Sorts columns by their binary offset position in the DB file. \"This is how RDBM exports tables\"\nDbMeta: Sorts columns based on the order defined in the DB metadata (XML) file.\"The first column is always the primary key\"\nColumn order has no impact on table validity, it's a matter of preference.", 
                           "formats": {"AsRead": ["underline"], "BitOffset": ["underline"], "DbMeta": ["underline"], "\"This is how FET exports tables\"": ["highlight"], "\"This is how RDBM exports tables\"": ["highlight"], "\"The first column is always the primary key\"": ["highlight"]},
                           "position": ToolTipPosition.TOP, "delay": 600},
    "getRecordsOptions": {"text": "Written Records Only: Get only records that have been written and excluding defaults records.\nTotal Records: Get all records including both written and defaults (unwritten). \"This is how RDBM exports tables\"",
                          "formats": {"Written Records Only": ["underline"], "Total Records": ["underline"], "\"This is how RDBM exports tables\"": ["highlight"]}, 
                          "position": ToolTipPosition.BOTTOM, "delay": 600},
    
    # Tables Changelogs Settings
    "resetAllChangelogsSettings": {"text": "Reset all changelogs settings to default values.", "position": ToolTipPosition.TOP, "delay": 880},

    # Advanced Settings
    "cacheUpToDate": {"text": "Cache is up to date.", "position": ToolTipPosition.TOP, "delay": 880},
    "cacheOutOfDate": {"text": "Cache is out of date.", "position": ToolTipPosition.TOP, "delay": 880},
    "": {"text": "", "position": ToolTipPosition.TOP, "delay": 880},

    "mod_enabled_dot": {
        "text": "This mod is enabled in the selected profile.",
        "formats": {"enabled": {"color": "green"}},
        "position": ToolTipPosition.TOP,
        "delay": 600
    },
    "mod_disabled_dot": {
        "text": "This mod is disabled in the selected profile.",
        "formats": {"disabled": {"color": "red"}},
        "position": ToolTipPosition.TOP,
        "delay": 600
    },
    "stats_total_mods": {
        "text": "The total number of mods found for the current game.",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },
    "stats_enabled_mods": {
        "text": "The number of mods currently enabled in the selected profile.",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },
    "stats_disabled_mods": {
        "text": "The number of mods currently disabled in the selected profile.",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },
    "stats_compatible_mods": {
        "text": "Mods that are fully compatible with your game's current Title Update.",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },
    "stats_uncertain_mods": {
        "text": "Mods for a different TU that don't contain any legacy assets, they are most likely compatible but this is uncertain.",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },
    "stats_incompatible_mods": {
        "text": "Mods for a different TU that contain legacy assets, whose legacy assets inside will not work probably.",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },

    "locate_mod_button": {
        "text": "Locate the selected mod file.",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },

    "search_mod_button": {
        "text": "Search the selected mod on Google.",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },

    "open_fet_data_folder_tooltip": {
        "text": "Open the FIFA Editor Tool data folder.",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },

    "refresh_folder_list_tooltip": {
        "text": "Refresh",
        "position": ToolTipPosition.TOP,
        "delay": 600
    },

}