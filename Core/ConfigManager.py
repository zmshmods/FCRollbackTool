import os
import json
import winreg
import copy
from typing import Optional, Dict, Any, List, Callable

from Core.Logger import logger
from Core.AppDataManager import AppDataManager
from Core.ErrorHandler import ErrorHandler

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._config_updated_callbacks = []
        self.CONFIG_FILE = "config.json"
        self.ENCODING = "utf-8"
        self.JSON_INDENT = 4
        #self.path = self.CONFIG_FILE
        self.app_data_manager = AppDataManager()
        self.config_location = "APPDATA"
        if self.config_location == "APPDATA":
            self.path = os.path.join(self.app_data_manager.getDataFolder(), self.CONFIG_FILE)
        else:
            self.path = os.path.join(os.getcwd(), self.CONFIG_FILE)
        self._cached_config = None
        self.default_config = {
            "GameConfig": {
                "SelectedGame": None,
                "SHA1": None,
                "ManuallyAddedGames": []
            },
            "Settings": {
                "InstallationOptions": {
                    "BackupGameSettingsFolder": True,
                    "BackupTitleUpdate": False,
                    "DeleteStoredTitleUpdate": False,
                    "DeleteSquadsAfterInstall": False,
                    "DeleteLiveTuningUpdate": True
                },
                "DownloadOptions": {
                    "Segments": "8",
                    "SpeedLimitEnabled": False,
                    "SpeedLimit": None,
                    "AutoUseIDM": False,
                    "IDMPath": None,
                    "EnableDownloadLogs": True,
                    "LogDownloadProgress": False
                },
                "Visual": {
                    "LastUsedTab": "TitleUpdates",
                    "TableColumns": {
                        "TitleUpdates": ["SemVer", "ReleasedDate", "RelativeDate", "Size"],
                        "SquadsUpdates": ["ReleasedDate", "RelativeDate", "Size", "ReleasedOnTU"],
                        "FutSquadsUpdates": ["ReleasedDate", "RelativeDate", "Size", "ReleasedOnTU"]
                    },
                    "ContentVersionDisplay": {
                        "TitleUpdates": "VersionByNumber",
                        "SquadsUpdates": "VersionByDate",
                        "FutSquadsUpdates": "VersionByDate"
                    }
                },
                "Appearance": {
                    "WindowEffect": "Default"
                },
                "ShowMessageBoxes": {
                    "DownloadDisclaimer": True
                },
                "SquadsTablesFetcher": {
                    "ColumnOrder": "BitOffset",
                    "GetRecordsAs": "WrittenRecords",
                    "TableFormat": ".txt (UTF-8 BOM)",
                    "TableSavePath": "",
                    "FetchSquadsDB": False,
                    "SaveTablesInFolderUsingSquadFileName": True,
                    "SelectAllTables": True
                },
                "SquadsChangelogsFetcher": {
                    "ChangelogFormat": ".xlsx",
                    "ChangelogSavePath": "",
                    "SaveChangelogsInFolderUsingSquadFileName": True,
                    "SelectAllChangelogs": True
                }
            }
        }
        self.loadConfig()
        self._initialized = True

    def register_config_updated_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback to be invoked when the config changes."""
        if callback not in self._config_updated_callbacks:
            self._config_updated_callbacks.append(callback)
            logger.debug(f"Registered config updated callback: {callback}")

    def unregister_config_updated_callback(self, callback: Callable[[str], None]) -> None:
        """Unregister a callback."""
        if callback in self._config_updated_callbacks:
            self._config_updated_callbacks.remove(callback)
            logger.debug(f"Unregistered config updated callback: {callback}")

    def _notify_config_updated(self, table: str) -> None:
        """Invoke all registered callbacks with the specified table."""
        logger.debug(f"Notifying config updated for table: {table}, Number of callbacks: {len(self._config_updated_callbacks)}")
        for callback in self._config_updated_callbacks:
            try:
                callback(table)
                logger.debug(f"Called config updated callback for table: {table} on {callback}")
            except Exception as e:
                logger.error(f"Error in config updated callback for table {table}: {e}")

    def loadConfig(self, updates: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        #AppDataManager.manageTempFolder()
        os.makedirs(self.app_data_manager.getDataFolder(), exist_ok=True)
        if not os.path.exists(self.path):
            self.saveConfig(self.default_config)
        if self._cached_config is None:
            try:
                with open(self.path, "r", encoding=self.ENCODING) as f:
                    self._cached_config = json.load(f)
                logger.info("Config loaded successfully")
            except Exception as e:
                ErrorHandler.handleError(f"Error loading config file: {e}")
                self._cached_config = self.default_config.copy()
        if updates:
            config = self._cached_config
            for section, values in updates.items():
                if section in self.default_config and isinstance(values, dict):
                    if section == "Settings":
                        for sub_section, sub_values in values.items():
                            if sub_section in self.default_config["Settings"] and isinstance(sub_values, dict):
                                config.setdefault(section, {}).setdefault(sub_section, {}).update(
                                    {k: v for k, v in sub_values.items() if k in self.default_config["Settings"][sub_section]})
                    else:
                        config.setdefault(section, {}).update(
                            {k: v for k, v in values.items() if k in self.default_config[section]})
            self.saveConfig(config)
        return self._cached_config.copy()

    def saveConfig(self, config: Dict[str, Any]) -> None:
        try:
            os.makedirs(self.app_data_manager.getDataFolder(), exist_ok=True)
            with open(self.path, "w", encoding=self.ENCODING) as f:
                json.dump(config, f, indent=self.JSON_INDENT)
            logger.info(f"Config {'created' if not self._cached_config else 'updated'} successfully")
            self._cached_config = config.copy()
        except Exception as e:
            ErrorHandler.handleError(f"Error saving config file: {e}")

    def _set_config_value(self, section: str, key: str, value: Any, sub_section: str = None) -> None:
        config = self._cached_config.copy()
        if sub_section:
            config.setdefault(section, {}).setdefault(sub_section, {})[key] = value
        else:
            config.setdefault(section, {})[key] = value
        self.saveConfig(self._cached_config)

    def _get_config_value(self, section: str, key: str, default: Any = None, sub_section: str = None) -> Any:
        config = self._cached_config or self.default_config
        if sub_section:
            return config.get(section, {}).get(sub_section, {}).get(key, default)
        return config.get(section, {}).get(key, default)

    def getConfigKeySelectedGame(self) -> str: return self._get_config_value("GameConfig", "SelectedGame", "")
    def getConfigKeySHA1(self) -> Optional[str]: return self._get_config_value("GameConfig", "SHA1")
    def getConfigKeyManuallyAddedGames(self) -> List[str]: return self._get_config_value("GameConfig", "ManuallyAddedGames", [])
    def getConfigKeyBackupGameSettingsFolder(self) -> bool: return self._get_config_value("Settings", "BackupGameSettingsFolder", True, "InstallationOptions")
    def getConfigKeyBackupTitleUpdate(self) -> bool: return self._get_config_value("Settings", "BackupTitleUpdate", False, "InstallationOptions")
    def getConfigKeyDeleteStoredTitleUpdate(self) -> bool: return self._get_config_value("Settings", "DeleteStoredTitleUpdate", False, "InstallationOptions")
    def getConfigKeyDeleteSquadsAfterInstall(self) -> bool: return self._get_config_value("Settings", "DeleteSquadsAfterInstall", False, "InstallationOptions")
    def getConfigKeyDeleteLiveTuningUpdate(self) -> bool: return self._get_config_value("Settings", "DeleteLiveTuningUpdate", True, "InstallationOptions")
    def getConfigKeySegments(self) -> str: return self._get_config_value("Settings", "Segments", "8", "DownloadOptions")
    def getConfigKeySpeedLimitEnabled(self) -> bool: return self._get_config_value("Settings", "SpeedLimitEnabled", False, "DownloadOptions")
    def getConfigKeySpeedLimit(self) -> Optional[str]: return self._get_config_value("Settings", "SpeedLimit", None, "DownloadOptions")
    def getConfigKeyEnableDownloadLogs(self) -> bool: return self._get_config_value("Settings", "EnableDownloadLogs", True, "DownloadOptions")
    def getConfigKeyLogDownloadProgress(self) -> bool: return self._get_config_value("Settings", "LogDownloadProgress", False, "DownloadOptions")
    def getConfigKeyAutoUseIDM(self) -> bool: return self._get_config_value("Settings", "AutoUseIDM", False, "DownloadOptions")
    def getConfigKeyIDMPath(self) -> Optional[str]: return self._get_config_value("Settings", "IDMPath", None, "DownloadOptions")
    def getConfigKeyLastUsedTab(self) -> str: return self._get_config_value("Settings", "LastUsedTab", "TitleUpdates", "Visual")
    def getConfigKeyTableColumns(self, table: str, default_columns: List[str] = None) -> List[str]:
        defaults = self.default_config["Settings"]["Visual"]["TableColumns"]
        return self._get_config_value("Settings", "TableColumns", defaults, "Visual").get(table, default_columns or [])
    def getConfigKeyContentVersionDisplay(self, table: str) -> str:
        defaults = self.default_config["Settings"]["Visual"]["ContentVersionDisplay"]
        return self._get_config_value("Settings", "ContentVersionDisplay", defaults, "Visual").get(table, defaults.get(table))
    def getConfigKeyWindowEffect(self) -> str: return self._get_config_value("Settings", "WindowEffect", "Default", "Appearance")
    def getConfigKeyDownloadDisclaimer(self) -> bool: return self._get_config_value("Settings", "DownloadDisclaimer", True, "ShowMessageBoxes")

    def getConfigKeyColumnOrder(self) -> str: return self._get_config_value("Settings", "ColumnOrder", "BitOffset", "SquadsTablesFetcher")
    def getConfigKeyGetRecordsAs(self) -> str: return self._get_config_value("Settings", "GetRecordsAs", "WrittenRecords", "SquadsTablesFetcher")
    def getConfigKeyTableFormat(self) -> str: return self._get_config_value("Settings", "TableFormat", ".txt (UTF-8 BOM)", "SquadsTablesFetcher")
    def getConfigKeyTableSavePath(self) -> str: return self._get_config_value("Settings", "TableSavePath", "", "SquadsTablesFetcher")
    def getConfigKeyFetchSquadsDB(self) -> bool: return bool(self._get_config_value("Settings", "FetchSquadsDB", False, "SquadsTablesFetcher"))
    def getConfigKeySaveTablesInFolderUsingSquadFileName(self) -> bool: return bool(self._get_config_value("Settings", "SaveTablesInFolderUsingSquadFileName", True, "SquadsTablesFetcher"))
    def getConfigKeySelectAllTables(self) -> bool: return bool(self._get_config_value("Settings", "SelectAllTables", True, "SquadsTablesFetcher"))
    def getDefaultTableSettings(self) -> Dict[str, Any]: return self.default_config["Settings"]["SquadsTablesFetcher"].copy()

    def getConfigKeyChangelogFormat(self) -> str: return self._get_config_value("Settings", "ChangelogFormat", ".xlsx", "SquadsChangelogsFetcher")
    def getConfigKeyChangelogSavePath(self) -> str: return self._get_config_value("Settings", "ChangelogSavePath", "", "SquadsChangelogsFetcher")
    def getConfigKeySaveChangelogsInFolderUsingSquadFileName(self) -> bool: return bool(self._get_config_value("Settings", "SaveChangelogsInFolderUsingSquadFileName", True, "SquadsChangelogsFetcher"))
    def getConfigKeySelectAllChangelogs(self) -> bool: return bool(self._get_config_value("Settings", "SelectAllChangelogs", True, "SquadsChangelogsFetcher"))
    def getDefaultChangelogSettings(self) -> Dict[str, Any]: return self.default_config["Settings"]["SquadsChangelogsFetcher"].copy()

    def getContentVersionKey(self, tab_key: str) -> str:
        display_type = self.getConfigKeyContentVersionDisplay(tab_key)
        return {"TitleUpdates": "ContentVersion" if display_type == "VersionByNumber" else "ContentVersionDate", "SquadsUpdates": "SquadsContentVersion" if display_type == "VersionByNumber" else "SquadsContentVersionDate", "FutSquadsUpdates": "FutSquadsContentVersion" if display_type == "VersionByNumber" else "FutSquadsContentVersionDate"}.get(tab_key, "ContentVersion")
    
    def setConfigKeySelectedGame(self, game_path: str) -> None: self._set_config_value("GameConfig", "SelectedGame", game_path)
    def setConfigKeySHA1(self, sha1: str) -> None: self._set_config_value("GameConfig", "SHA1", sha1) 
    def setConfigKeyManuallyAddedGames(self, paths: List[str]) -> None: self._set_config_value("GameConfig", "ManuallyAddedGames", paths)
    def setConfigKeyBackupGameSettingsFolder(self, value: bool) -> None: self._set_config_value("Settings", "BackupGameSettingsFolder", value, "InstallationOptions")
    def setConfigKeyBackupTitleUpdate(self, value: bool) -> None: self._set_config_value("Settings", "BackupTitleUpdate", value, "InstallationOptions")
    def setConfigKeyDeleteStoredTitleUpdate(self, value: bool) -> None: self._set_config_value("Settings", "DeleteStoredTitleUpdate", value, "InstallationOptions")
    def setConfigKeyDeleteSquadsAfterInstall(self, value: bool) -> None: self._set_config_value("Settings", "DeleteSquadsAfterInstall", value, "InstallationOptions")
    def setConfigKeyDeleteLiveTuningUpdate(self, value: bool) -> None: self._set_config_value("Settings", "DeleteLiveTuningUpdate", value, "InstallationOptions")
    def setConfigKeySegments(self, value: str) -> None: self._set_config_value("Settings", "Segments", value, "DownloadOptions")
    def setConfigKeySpeedLimitEnabled(self, value: bool) -> None: self._set_config_value("Settings", "SpeedLimitEnabled", value, "DownloadOptions")
    def setConfigKeySpeedLimit(self, value: Optional[str]) -> None: self._set_config_value("Settings", "SpeedLimit", value, "DownloadOptions")
    def setConfigKeyEnableDownloadLogs(self, value: bool) -> None: self._set_config_value("Settings", "EnableDownloadLogs", value, "DownloadOptions")
    def setConfigKeyLogDownloadProgress(self, value: bool) -> None: self._set_config_value("Settings", "LogDownloadProgress", value, "DownloadOptions")
    def setConfigKeyAutoUseIDM(self, value: bool) -> None: self._set_config_value("Settings", "AutoUseIDM", value, "DownloadOptions")
    def setConfigKeyIDMPath(self, value: Optional[str]) -> None: self._set_config_value("Settings", "IDMPath", value, "DownloadOptions")
    def setConfigKeyLastUsedTab(self, tab: str) -> None: self._set_config_value("Settings", "LastUsedTab", tab, "Visual")
    def setConfigKeyTableColumns(self, table: str, columns: List[str]) -> None:
        if self._cached_config is None:
            self._cached_config = self.loadConfig()
        config = self._cached_config.copy()
        visual_settings = config.get("Settings", {}).get("Visual", {})
        table_columns = visual_settings.get("TableColumns", self.default_config["Settings"]["Visual"]["TableColumns"].copy())
        table_columns[table] = columns
        self._set_config_value("Settings", "TableColumns", table_columns, "Visual")
        self._notify_config_updated(table)

    def setConfigKeyContentVersionDisplay(self, table: str, display_type: str) -> None:
        if display_type in ["VersionByNumber", "VersionByDate"]:
            if self._cached_config is None:
                self._cached_config = self.loadConfig()
            config = self._cached_config.copy()
            visual_settings = config.get("Settings", {}).get("Visual", {})
            content_display = visual_settings.get("ContentVersionDisplay", self.default_config["Settings"]["Visual"]["ContentVersionDisplay"].copy())
            content_display[table] = display_type
            self._set_config_value("Settings", "ContentVersionDisplay", content_display, "Visual")
            self._notify_config_updated(table)
            
    def setConfigKeyWindowEffect(self, effect: str) -> None: self._set_config_value("Settings", "WindowEffect", effect, "Appearance")
    def setConfigKeyDownloadDisclaimer(self, value: bool) -> None: self._set_config_value("Settings", "DownloadDisclaimer", value, "ShowMessageBoxes")

    def setConfigKeyColumnOrder(self, value: str) -> None: self._set_config_value("Settings", "ColumnOrder", value, "SquadsTablesFetcher")
    def setConfigKeyGetRecordsAs(self, value: str) -> None: self._set_config_value("Settings", "GetRecordsAs", value, "SquadsTablesFetcher")
    def setConfigKeyTableFormat(self, value: str) -> None: self._set_config_value("Settings", "TableFormat", value, "SquadsTablesFetcher")
    def setConfigKeyTableSavePath(self, value: str) -> None: self._set_config_value("Settings", "TableSavePath", value, "SquadsTablesFetcher")
    def setConfigKeyFetchSquadsDB(self, value: bool) -> None: self._set_config_value("Settings", "FetchSquadsDB", value, "SquadsTablesFetcher")
    def setConfigKeySaveTablesInFolderUsingSquadFileName(self, value: bool) -> None: self._set_config_value("Settings", "SaveTablesInFolderUsingSquadFileName", value, "SquadsTablesFetcher")
    def setConfigKeySelectAllTables(self, value: bool) -> None: self._set_config_value("Settings", "SelectAllTables", value, "SquadsTablesFetcher")

    def setConfigKeyChangelogFormat(self, value: str) -> None: self._set_config_value("Settings", "ChangelogFormat", value, "SquadsChangelogsFetcher")
    def setConfigKeyChangelogSavePath(self, value: str) -> None: self._set_config_value("Settings", "ChangelogSavePath", value, "SquadsChangelogsFetcher")
    def setConfigKeySaveChangelogsInFolderUsingSquadFileName(self, value: bool) -> None: self._set_config_value("Settings", "SaveChangelogsInFolderUsingSquadFileName", value, "SquadsChangelogsFetcher")
    def setConfigKeySelectAllChangelogs(self, value: bool) -> None: self._set_config_value("Settings", "SelectAllChangelogs", value, "SquadsChangelogsFetcher")  
         
    def resetSelectedGame(self) -> None:
        try:
            if self.getConfigKeySelectedGame():
                self._set_config_value("GameConfig", "SelectedGame", None)
                self._set_config_value("GameConfig", "SHA1", None)
                logger.info("Selected game reset")
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting selected game: {e}")
        
    def getIDMPathFromRegistry(self) -> Optional[str]:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\DownloadManager") as key:
                idm_path, _ = winreg.QueryValueEx(key, "ExePath")
            return idm_path if os.path.exists(idm_path) else None
        except Exception:
            logger.warning("IDM registry key not found")
            return None

    def resetAllSettingsToDefault(self) -> None:
        """Reset the entire 'Settings' tree to its default values."""
        try:
            config = copy.deepcopy(self.default_config)
            if self._cached_config:
                for section in self._cached_config:
                    if section != "Settings":
                        config[section] = copy.deepcopy(self._cached_config[section])
            self._cached_config = config
            self.saveConfig(config)
            # Notify all relevant tables after resetting all settings
            tables = ["TitleUpdates", "SquadsUpdates", "FutSquadsUpdates"]
            for table in tables:
                self._notify_config_updated(table)
            logger.info("All settings reset to default")
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting all settings: {str(e)}")

    def resetInstallationOptions(self) -> None:
        """Reset InstallationOptions tree to its default values."""
        try:
            config = copy.deepcopy(self._cached_config if self._cached_config else self.default_config)
            config["Settings"]["InstallationOptions"] = copy.deepcopy(self.default_config["Settings"]["InstallationOptions"])
            self._cached_config = config
            self.saveConfig(config)
            logger.info("InstallationOptions settings reset to default")
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting InstallationOptions: {str(e)}")

    def resetDownloadOptions(self) -> None:
        """Reset DownloadOptions tree to its default values."""
        try:
            config = copy.deepcopy(self._cached_config if self._cached_config else self.default_config)
            config["Settings"]["DownloadOptions"] = copy.deepcopy(self.default_config["Settings"]["DownloadOptions"])
            self._cached_config = config
            self.saveConfig(config)
            logger.info("DownloadOptions settings reset to default")
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting DownloadOptions: {str(e)}")

    def resetVisual(self, sub_section: Optional[str] = None) -> None:
        """Reset Visual tree or a specific sub-section to its default values."""
        try:
            config = copy.deepcopy(self._cached_config if self._cached_config else self.default_config)
            default_visual = copy.deepcopy(self.default_config["Settings"]["Visual"])
            if sub_section in ["TableColumns", "ContentVersionDisplay", "LastUsedTab"]:
                config["Settings"]["Visual"][sub_section] = default_visual[sub_section]
            else:
                config["Settings"]["Visual"] = default_visual
            self._cached_config = config
            self.saveConfig(config)
            # Notify all relevant tables when resetting TableColumns or ContentVersionDisplay
            if sub_section in ["TableColumns", "ContentVersionDisplay"]:
                tables = ["TitleUpdates", "SquadsUpdates", "FutSquadsUpdates"]
                for table in tables:
                    self._notify_config_updated(table)
            else:
                self._notify_config_updated(f"Visual_{sub_section or 'all'}")
            logger.info(f"Visual settings reset to default (sub_section: {sub_section or 'all'})")
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting Visual settings: {str(e)}")

    def resetAppearance(self) -> None:
        """Reset Appearance tree to its default values."""
        try:
            config = copy.deepcopy(self._cached_config if self._cached_config else self.default_config)
            config["Settings"]["Appearance"] = copy.deepcopy(self.default_config["Settings"]["Appearance"])
            self._cached_config = config
            self.saveConfig(config)
            logger.info("Appearance settings reset to default")
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting Appearance: {str(e)}")

    def resetShowMessageBoxes(self) -> None:
        """Reset ShowMessageBoxes tree to its default values."""
        try:
            config = copy.deepcopy(self._cached_config if self._cached_config else self.default_config)
            config["Settings"]["ShowMessageBoxes"] = copy.deepcopy(self.default_config["Settings"]["ShowMessageBoxes"])
            self._cached_config = config
            self.saveConfig(config)
            logger.info("ShowMessageBoxes settings reset to default")
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting ShowMessageBoxes: {str(e)}")

    def resetTableSettingsToDefault(self) -> None:
        """Reset SquadsTablesFetcher tree to its default values."""
        try:
            config = copy.deepcopy(self._cached_config if self._cached_config else self.default_config)
            config["Settings"]["SquadsTablesFetcher"] = copy.deepcopy(self.default_config["Settings"]["SquadsTablesFetcher"])
            self._cached_config = config
            self.saveConfig(config)
            logger.info("SquadsTablesFetcher settings reset to default")
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting SquadsTablesFetcher settings: {str(e)}")

    def resetChangelogSettings(self) -> None:
        """Reset SquadsChangelogsFetcher tree to its default values."""
        try:
            config = copy.deepcopy(self._cached_config if self._cached_config else self.default_config)
            config["Settings"]["SquadsChangelogsFetcher"] = copy.deepcopy(self.default_config["Settings"]["SquadsChangelogsFetcher"])
            self._cached_config = config
            self.saveConfig(config)
            logger.info("SquadsChangelogsFetcher settings reset to default")
        except Exception as e:
            ErrorHandler.handleError(f"Error resetting SquadsChangelogsFetcher settings: {str(e)}")