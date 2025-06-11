import os, re, json, winreg, hashlib, requests, pickle, zlib, shutil, copy, traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
import win32api
import win32con
import xml.etree.ElementTree as ET
from Core.Logger import logger
from Core.Logger import logger
try:
    from Core.key import key  # type: ignore
except ModuleNotFoundError:
    key = None
    logger.warning("Core.key module not available in the source code.")

GITHUB_ACC = "zmshmods"
GITHUB_ACC_TOOL = "FCRollbackTool"
MAIN_REPO = "FCRollbackTool"
UPDATES_REPO = "FCRollbackToolUpdates"

class ToolUpdateManager:
    def __init__(self):
        self.TOOL_VERSION = "1.2.0 Beta"
        self.BUILD_VERSION = "3.2025.06.11"
        self.UPDATE_MANIFEST = f"https://raw.githubusercontent.com/{GITHUB_ACC}/{UPDATES_REPO}/main/toolupdate.json"
        self.CHANGELOG_BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_ACC}/{UPDATES_REPO}/main/Changelogs/"
        self._manifest_cache = {}
        self._changelog_cache = {}

    def getToolVersion(self) -> str:
        return self.TOOL_VERSION
    def getToolBulidVersion(self) -> str:
        return self.BUILD_VERSION
# --
    def FetchManifests(self) -> None:
        try:
            response = requests.get(self.UPDATE_MANIFEST, timeout=10)
            response.raise_for_status()
            self._manifest_cache = response.json()
            logger.debug("Fetched toolupdate manifest data")
        except Exception as e:
            logger.error(f"Error fetching manifest for toolupdate: {e}")
            self._manifest_cache = {}
    def getManifestToolVersion(self) -> str:
        if not self._manifest_cache:
            self.FetchManifests()
        return self._manifest_cache.get("ToolUpdate", {}).get("ToolVersion", "Unknown Version")
    def getManifestBuildVersion(self) -> str:
        if not self._manifest_cache:
            self.FetchManifests()
        return self._manifest_cache.get("ToolUpdate", {}).get("BulidVersion", "Unknown Build Version")
    def getMatchingVersion(self) -> bool:
        return self.getToolVersion() == self.getManifestToolVersion()
    def getToolChangelog(self) -> list:
        try:
            if self.TOOL_VERSION not in self._changelog_cache:
                response = requests.get(f"{self.CHANGELOG_BASE_URL}{self.TOOL_VERSION}.txt", timeout=10)
                response.raise_for_status()
                self._changelog_cache[self.TOOL_VERSION] = response.text.splitlines()
            return self._changelog_cache[self.TOOL_VERSION]
        except Exception as e:
            logger.error(f"Error fetching app changelog: {e}")
            return ["- Unable to fetch changelog"]
    def getDownloadUrl(self) -> str:
        if not self._manifest_cache:
            self.FetchManifests()
        return self._manifest_cache.get("ToolUpdate", {}).get("DownloadLink", None)
#--
    def getManifestChangelog(self) -> list:
        try:
            version = self.getManifestToolVersion()
            if version not in self._changelog_cache:
                response = requests.get(f"{self.CHANGELOG_BASE_URL}{version}.txt", timeout=10)
                response.raise_for_status()
                self._changelog_cache[version] = response.text.splitlines()
            return self._changelog_cache[version]
        except Exception as e:
            logger.error(f"Error fetching manifest changelog: {e}")
            return ["- Unable to fetch changelog"]

class MainDataManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MainDataManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.basePath = os.path.join(os.getcwd(), "Data")
        self.meta_cache: Dict[str, Dict] = {}
        self._initialized = True

    def getPath(self, subPath: str) -> Optional[str]:
        path = os.path.join(self.basePath, subPath)
        if not os.path.exists(path):
            ErrorHandler.handleError(f"'{subPath}' not found at: {path}")
            return None
        logger.debug(f"Retrieved {subPath}: {path}")
        return path

    def getAria2c(self) -> str: return self.getPath("ThirdParty/aria2c.exe")
    def getUnRAR(self) -> str: return self.getPath("ThirdParty/UnRAR.exe")
    def getIcons(self) -> str: return self.getPath("Assets/Icons")
    def getBaseCache(self) -> str: return self.getPath("BaseCache")
    def getKey(self) -> str: return key
    def getCompressedFileExtensions(self) -> List[str]: return [".rar", ".zip", ".7z"]
    def getDbMeta(self, game_version: str, squad_type: str) -> Dict:
        """Load and cache metadata from XML based on game version and squad type."""
        cache_key = f"{game_version}_{squad_type}"
        if cache_key in self.meta_cache:
            #logger.debug(f"Returning cached metadata for {cache_key}, game: {game_version}, squad_type: {squad_type}")
            return self.meta_cache[cache_key]

        xml_file = f"fifa_ng_db-meta.xml" if squad_type == "Squads" else "cards_ng_db-meta.xml"
        xml_path = self.getPath(os.path.join("DB", game_version.upper(), xml_file))
        if not xml_path:
            ErrorHandler.handleError(f"Metadata file not found: {xml_file} for {game_version}")
            return {}

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            meta_data = {}
            for table in root.findall("table"):
                table_name = table.get("name")
                short_name = table.get("shortname")
                fields = [
                    {
                        "name": field.get("name"),
                        "shortname": field.get("shortname")
                    }
                    for field in table.find("fields").findall("field")
                ]
                meta_data[table_name] = {"shortname": short_name, "fields": fields}
                meta_data[short_name] = {"name": table_name, "fields": fields}
            
            self.meta_cache[cache_key] = meta_data
            logger.debug(f"Cached metadata for {cache_key}")
            return meta_data
        except Exception as e:
            ErrorHandler.handleError(f"Error parsing metadata file {xml_file} for {game_version}: {e}")
            return {}

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
        self.config_location = "APPDATA"  # can be "LOCAL" 
        if self.config_location == "APPDATA":
            self.path = os.path.join(self.app_data_manager.getDataFolder(), self.CONFIG_FILE)
        else:
            self.path = os.path.join(os.getcwd(), self.CONFIG_FILE)
        self._cached_config = None
        self.default_config = {
            "GameConfig": {
                "SelectedGame": None,
                "SHA1": None
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
        self.saveConfig(config)

    def _get_config_value(self, section: str, key: str, default: Any = None, sub_section: str = None) -> Any:
        config = self._cached_config or self.default_config
        if sub_section:
            return config.get(section, {}).get(sub_section, {}).get(key, default)
        return config.get(section, {}).get(key, default)

    def getConfigKeySelectedGame(self) -> str: return self._get_config_value("GameConfig", "SelectedGame", "")
    def getConfigKeySHA1(self) -> Optional[str]: return self._get_config_value("GameConfig", "SHA1")
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

    def getConfigKeyChangelogFormat(self) -> str:return self._get_config_value("Settings", "ChangelogFormat", ".xlsx", "SquadsChangelogsFetcher")
    def getConfigKeyChangelogSavePath(self) -> str: return self._get_config_value("Settings", "ChangelogSavePath", "", "SquadsChangelogsFetcher")
    def getConfigKeySaveChangelogsInFolderUsingSquadFileName(self) -> bool: return bool(self._get_config_value("Settings", "SaveChangelogsInFolderUsingSquadFileName", True, "SquadsChangelogsFetcher"))
    def getConfigKeySelectAllChangelogs(self) -> bool: return bool(self._get_config_value("Settings", "SelectAllChangelogs", True, "SquadsChangelogsFetcher"))
    def getDefaultChangelogSettings(self) -> Dict[str, Any]: return self.default_config["Settings"]["SquadsChangelogsFetcher"].copy()

    def getContentVersionKey(self, tab_key: str) -> str:
        display_type = self.getConfigKeyContentVersionDisplay(tab_key)
        return {"TitleUpdates": "ContentVersion" if display_type == "VersionByNumber" else "ContentVersionDate", "SquadsUpdates": "SquadsContentVersion" if display_type == "VersionByNumber" else "SquadsContentVersionDate", "FutSquadsUpdates": "FutSquadsContentVersion" if display_type == "VersionByNumber" else "FutSquadsContentVersionDate"}.get(tab_key, "ContentVersion")
    
    def setConfigKeySelectedGame(self, game_path: str) -> None: self._set_config_value("GameConfig", "SelectedGame", game_path)
    def setConfigKeySHA1(self, sha1: str) -> None: self._set_config_value("GameConfig", "SHA1", sha1) 
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

class GameManager:
    def __init__(self):
        self.PROFILES_DIR = "Profiles"
        self.TIMEOUT = 7
        self.MAX_RETRIES = 2
        self.GAME_PUBLISHER_NAME = "EA SPORTS"
        self.GAME_PREFIX = "FC"
        self.GAME_VERSION = ["25", "24"]
        self.SHORT_GAME_NAME = f"{self.GAME_PREFIX}{self.GAME_VERSION[0]}"
        self.GAME_PATHS = {
            f"{self.GAME_PREFIX}{version}": {
                "SettingsBase": os.path.expandvars(rf"%localappdata%\{self.GAME_PUBLISHER_NAME} {self.GAME_PREFIX} {version}") if version != "24" else os.path.expanduser(rf"~\Documents\{self.GAME_PREFIX} {version}"),
                "LiveTuningBase": os.path.expandvars(rf"%localappdata%\Temp\{self.GAME_PUBLISHER_NAME} {self.GAME_PREFIX} {version}") if version != "24" else os.path.expandvars(rf"%localappdata%\Temp\{self.GAME_PREFIX} {version}")
            } for version in self.GAME_VERSION
        }
        self._profile_types = ["TitleUpdates", "SquadsUpdates"]
        self._content_keys = ["TitleUpdates", "Squads", "FutSquads"]
        self.profiles_base_url = f"https://raw.githubusercontent.com/{GITHUB_ACC}/{UPDATES_REPO}/main/Profiles/"
        self.title_updates_keys = ["ContentVersion", "ContentVersionDate", "AppID", "MainDepotID", "eng_usDepotID", "Name", "SemVer", "ReleasedDate", "RelativeDate", "Size", "MainManifestID", "eng_usManifestID", "PatchNotes", "SHA1", "DownloadURL"]
        self.squads_keys = ["SquadsContentVersion", "SquadsContentVersionDate", "Name", "ReleasedDate", "RelativeDate", "BuildDate", "ReleasedOnTU", "Size", "dbMajor", "DownloadURL"]
        self.fut_squads_keys = ["FutSquadsContentVersion", "FutSquadsContentVersionDate", "Name", "ReleasedDate", "RelativeDate", "BuildDate", "ReleasedOnTU", "Size", "dbFUTVer", "DownloadURL"]
        self.excluded_column_keys = ["SHA1", "MainDepotID", "eng_usDepotID", "AppID", "ContentVersionDate", "ContentVersion", "FutSquadsContentVersionDate", "FutSquadsContentVersion", "SquadsContentVersionDate", "SquadsContentVersion", "DownloadURL", "PatchNotes"]
        self._content_cache = {}
        self._profile_dir_cache = {}
        self.is_offline = False
        self.app_data_manager = AppDataManager()
        self.main_data_manager = MainDataManager()  # Singleton instance
        os.makedirs(self.app_data_manager.getDataFolder(), exist_ok=True)
        self._index_cache = {}  # Cache for Index.json data that uses for squads/fut
        self._live_editor_versions_cache = {}  # Cache for live editor version.json data
    
    def getTitleUpdateSHA1Key(self) -> str: return "SHA1"
    def getTitleUpdateContentVersionKey(self) -> str: return "ContentVersion"
    def getTitleUpdateContentVersionDateKey(self) -> str: return "ContentVersionDate"
    def getTitleUpdateAppIDKey(self) -> str: return "AppID"
    def getTitleUpdateMainDepotIDKey(self) -> str: return "MainDepotID"
    def getTitleUpdateEngUsDepotIDKey(self) -> str: return "eng_usDepotID"
    def getTitleUpdateNameKey(self) -> str: return "Name"
    def getTitleUpdateSemVerKey(self) -> str: return "SemVer"
    def getTitleUpdateSizeKey(self) -> str: return "Size"
    def getTitleUpdateReleasedDateKey(self) -> str: return "ReleasedDate"
    def getTitleUpdateRelativeDateKey(self) -> str: return "RelativeDate"
    def getTitleUpdateDownloadURLKey(self) -> str: return "DownloadURL"
    def getTitleUpdateMainManifestIDKey(self) -> str: return "MainManifestID"
    def getTitleUpdateEngUsManifestIDKey(self) -> str: return "eng_usManifestID"
    def getTitleUpdatePatchNotesKey(self) -> str: return "PatchNotes"
    def getSquadsContentVersionKey(self) -> str: return "SquadsContentVersion"
    def getSquadsContentVersionDateKey(self) -> str: return "SquadsContentVersionDate"
    def getSquadsNameKey(self) -> str: return "Name"
    def getSquadsSizeKey(self) -> str: return "Size"
    def getSquadsReleasedDateKey(self) -> str: return "ReleasedDate"
    def getSquadsRelativeDateKey(self) -> str: return "RelativeDate"
    def getSquadsBuildDateKey(self) -> str: return "BuildDate"
    def getSquadsReleasedOnTUKey(self) -> str: return "ReleasedOnTU"
    def getSquadsDownloadURLKey(self) -> str: return "DownloadURL"
    def getSquadsDbMajorKey(self) -> str: return "dbMajor"
    def getFutSquadsContentVersionKey(self) -> str: return "FutSquadsContentVersion"
    def getFutSquadsContentVersionDateKey(self) -> str: return "FutSquadsContentVersionDate"
    def getFutSquadsNameKey(self) -> str: return "Name"
    def getFutSquadsSizeKey(self) -> str: return "Size"
    def getFutSquadsReleasedDateKey(self) -> str: return "ReleasedDate"
    def getFutSquadsRelativeDateKey(self) -> str: return "RelativeDate"
    def getFutSquadsBuildDateKey(self) -> str: return "BuildDate"
    def getFutSquadsReleasedOnTUKey(self) -> str: return "ReleasedOnTU"
    def getFutSquadsDownloadURLKey(self) -> str: return "DownloadURL"
    def getFutSquadsDbFUTVerKey(self) -> str: return "dbFUTVer"
    def getDownloadURLKeyForTab(self, tab_key: str) -> str:
        if tab_key == self.getTabKeyTitleUpdates(): return self.getTitleUpdateDownloadURLKey()
        elif tab_key == self.getTabKeySquadsUpdates(): return self.getSquadsDownloadURLKey()
        elif tab_key == self.getTabKeyFutSquadsUpdates(): return self.getFutSquadsDownloadURLKey()
        raise ValueError(f"Invalid tab_key: {tab_key}")

    def getTabKeyTitleUpdates(self) -> str: return "TitleUpdates"
    def getTabKeySquadsUpdates(self) -> str: return "SquadsUpdates"
    def getTabKeyFutSquadsUpdates(self) -> str: return "FutSquadsUpdates"

    def getRelativeDate(self, date_str: str, is_title_update: bool = False) -> str:
        """Convert date string to relative time."""
        try:
            dt = datetime.strptime(date_str, "%b %d, %Y").replace(
                hour=9 if is_title_update else 0, minute=0, second=0, tzinfo=timezone.utc
            )
            delta = (dt - datetime.now(timezone.utc)).total_seconds()
            seconds = abs(delta)
            is_future = delta > 0
            prefix, suffix = ("In ", "") if is_future else ("", " ago")

            units = [
                (31557600, "Year", lambda s: f"{s / 31557600:.1f}"),
                (2592000, "Month", lambda s: f"{s / 2592000:.1f}"),
                (86400, "Day", lambda s: f"{int(s / 86400)}"),
                (3600, "Hour", lambda s: f"{round(s / 3600)}"),
                (60, "Minute", lambda s: f"{int(s / 60)}"),
                (1, "Second", lambda s: f"{int(s)}"),
            ]

            for limit, unit, fmt in units:
                if seconds >= limit:
                    value = fmt(seconds)
                    if value.endswith(".0"):
                        value = value[:-2]
                    unit = unit if value == "1" or unit == "Month" and "." not in value else unit + "s"
                    return f"{prefix}{value} {unit}{suffix}"
            return "Now"
        except ValueError as e:
            logger.error(f"Failed to parse date {date_str}: {e}")
            return "Invalid Date"

    def getDbExtension(self) -> str:
        return ".db"
    def getTableExtension(self) -> str:
        return ".csv"
    def getChangelogsExtension(self) -> str:
        return ".xlsx"
    
    def fetchIndexData(self, index_url: str) -> Optional[Dict]:
        """Fetch and cache Index.json data."""
        if index_url in self._index_cache:
            return self._index_cache[index_url]
        
        try:
            response = requests.get(index_url, timeout=self.TIMEOUT)
            response.raise_for_status()
            index_data = response.json()
            self._index_cache[index_url] = index_data
            return index_data
        except requests.RequestException as e:
            ErrorHandler.handleError(f"Failed to fetch Index.json from {index_url}: {e}")
            return None

    def getTablesData(self, index_url: str) -> Optional[List[Dict]]:
        """Get the list of tables from Index.json."""
        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        tables = index_data.get("Databases", [{}])[0].get("Tables", [])
        tables.sort(key=lambda x: x.get("Name", "").lower()) # Sort tables by name
        return tables

    def getChangelogsData(self, index_url: str) -> Optional[List[Dict]]:
        """Fetch and return the list of changelogs from Index.json."""
        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        changelogs = index_data.get("Databases", [{}])[0].get("Changelogs", {}).get("Files", [])
        return changelogs

    def getTablesPath(self, index_url: str) -> Optional[str]:
        """Get the TablesPath from Index.json."""
        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        tables_path = index_data.get("Databases", [{}])[0].get("TablesPath")
        if not tables_path:
            ErrorHandler.handleError(f"TablesPath not found in Index.json: {index_url}")
            return None
        return tables_path

    def getChangelogsPath(self, index_url: str) -> Optional[str]:
        """Get the Changelogs Path from Index.json."""
        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        changelogs_path = index_data.get("Databases", [{}])[0].get("Changelogs", {}).get("Path")
        if not changelogs_path:
            ErrorHandler.handleError(f"Changelogs Path not found in Index.json: {index_url}")
            return None
        return changelogs_path

    def getSquadsBaseURL(self, game_version: str) -> str:
        """Get the squads base URL based on the game version."""
        return f"https://raw.githubusercontent.com/{GITHUB_ACC_TOOL}/{self.GAME_PREFIX}{game_version}Squads/main"

    def getTableUrl(self, index_url: str, table_name: str, config_mgr: ConfigManager) -> Optional[str]:
        """Get the full URL for a specific table based on the selected game."""
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected")
            return None
        game_version = self.getShortGameName(game_path).replace(self.GAME_PREFIX, "")
        tables_path = self.getTablesPath(index_url)
        if not tables_path:
            return None
        return f"{self.getSquadsBaseURL(game_version)}/{tables_path}/{table_name}{self.getTableExtension()}"

    def getChangelogUrl(self, index_url: str, changelog_name: str, config_mgr: ConfigManager) -> Optional[str]:
        """Get the full URL for a specific changelog based on the selected game."""
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected")
            return None
        game_version = self.getShortGameName(game_path).replace(self.GAME_PREFIX, "")
        changelogs_path = self.getChangelogsPath(index_url)
        if not changelogs_path:
            return None
        clean_changelog_name = changelog_name.replace(self.getChangelogsExtension(), "")
        return f"{self.getSquadsBaseURL(game_version)}/{changelogs_path}/{clean_changelog_name}{self.getChangelogsExtension()}"

    def getSquadFilePathKey(self, index_url: str, config_mgr: ConfigManager) -> Optional[str]:
        """Fetch and construct full SquadFilePath URL from Index.json."""
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected")
            return None
        game_version = self.getShortGameName(game_path).replace(self.GAME_PREFIX, "")
        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        squad_file_path = index_data.get("SquadFilePath")
        if not squad_file_path:
            ErrorHandler.handleError(f"SquadFilePath not found in Index.json: {index_url}")
            return None
        return f"{self.getSquadsBaseURL(game_version)}/{squad_file_path}"

    def getDbName(self, index_url: str) -> Optional[str]:
        """Get the DbName value from Index.json."""
        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        db_name = index_data.get("Databases", [{}])[0].get("DbName")
        if not db_name:
            ErrorHandler.handleError(f"DbName not found in Index.json: {index_url}")
        return db_name
    
    def getDbPathKey(self, index_url: str, config_mgr: ConfigManager) -> Optional[str]:
        """Fetch and construct full DbPath URL from Index.json."""
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected")
            return None
        game_version = self.getShortGameName(game_path).replace(self.GAME_PREFIX, "")
        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        db_path = index_data.get("Databases", [{}])[0].get("DbPath")
        if not db_path:
            ErrorHandler.handleError(f"DbPath not found in Index.json: {index_url}")
            return None
        return f"{self.getSquadsBaseURL(game_version)}/{db_path}"

    def getTableCount(self, index_url: str) -> Optional[int]:
        """Get the TableCount value from Index.json."""
        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        table_count = index_data.get("Databases", [{}])[0].get("TableCount")
        if table_count is None:
            logger.warning(f"TableCount not found in Index.json: {index_url}")
        return table_count
    
    def getTableURL(self, index_url: str, table_name: str = None, config_mgr: ConfigManager = None) -> Optional[str]:
       # full URL from Index.json
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected")
            return None
        game_version = self.getShortGameName(game_path).replace(self.GAME_PREFIX, "")
        tables_path = self.getTablesPath(index_url)
        if not tables_path:
            return None
        full_path = f"{self.getSquadsBaseURL(game_version)}/{tables_path}"
        if table_name:
            full_path = f"{full_path}/{table_name}{self.getTableExtension()}"
        return full_path

    def getDatabaseCountKey(self) -> str: return "DatabaseCount"
    def getDbNameKey(self) -> str: return "DbName"
    def getTableCountKey(self) -> str: return "TableCount"
    def getTableNameKey(self) -> str: return "Name"
    def getTableShortNameKey(self) -> str: return "ShortName"
    def getTableSaveGroupsKey(self) -> str: return "SaveGroups"
    def getTableRecordSizeKey(self) -> str: return "RecordSize"
    def getTableTotalRecordsKey(self) -> str: return "TotalRecords"
    def getTableWrittenRecordsKey(self) -> str: return "WrittenRecords"
    def getTableColumnReadOrder(self) -> str: return "ColumnReadOrder"
    def getTableColumnReadOrder(self) -> str: return "DefaultRecord"
    def getChangelogsFilesKey(self) -> str: return "Files"
    def getChangelogTypeKey(self) -> str: return "Type"
    def getChangelogFileNameKey(self) -> str: return "FileName"
    def getChangelogCountsKey(self) -> str: return "Counts"
    def getChangelogCountsAddedKey(self) -> str: return "Added"
    def getChangelogCountsRemovedKey(self) -> str: return "Removed"
    def getChangelogCountsModifiedKey(self) -> str: return "Modified"
    def getChangelogCountsHeadModelsAddedKey(self) -> str: return "HeadModels_Added"
    def getChangelogCountsHeadModelsRemovedKey(self) -> str: return "HeadModels_Removed"
    def getChangelogCountsCraniumFacesUpdatesKey(self) -> str: return "CraniumFacesUpdates"
    def getChangelogCountsTransfersFreeKey(self) -> str: return "Transfers_Free"
    def getChangelogCountsTransfersPermanentKey(self) -> str: return "Transfers_Permanent"
    def getChangelogCountsTransfersLoanKey(self) -> str: return "Transfers_Loan"
    def getChangelogCountsNationalTeamsCalledUpKey(self) -> str: return "NationalTeams_CalledUp"
    def getChangelogCountsManagerTrackerAppointedKey(self) -> str: return "ManagerTracker_Appointed"
    def getChangelogCountsManagerTrackerReAppointedKey(self) -> str: return "ManagerTracker_ReAppointed"
    def getChangelogCountsManagerTrackerDepartedKey(self) -> str: return "ManagerTracker_Departed"
    def getChangelogCountsGenericHeadModelsAddedKey(self) -> str: return "GenericHeadModels_Added"
    def getChangelogCountsGenericHeadModelsRemovedKey(self) -> str: return "GenericHeadModels_Removed"

    def getSquadTypeFromIndexUrl(self, index_url: str) -> str:
        """Determine squad type (Squads or FutSquads) based on index_url."""
        if "FutSquads" in index_url:
            return "FutSquads"
        return "Squads"
    # DB Meta Getters
    def getColumnMetaName(self, table_name: str, short_name: str, config_mgr: ConfigManager, squad_type: str = "Squads") -> Optional[str]:
        """Get column name for a given shortname in a table from metadata based on selected game and squad type."""
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected")
            return None
        game_version = self.getShortGameName(game_path).lower()
        meta = self.main_data_manager.getDbMeta(game_version, squad_type)
        table_data = meta.get(table_name)
        if table_data:
            for field in table_data["fields"]:
                if field["shortname"] == short_name:
                    return field["name"]
        return None

    def getTableMetaColumnOrder(self, table_name: str, config_mgr: ConfigManager, squad_type: str = "Squads") -> Optional[List[str]]:
        """Get the order of columns for a given table from metadata based on selected game and squad type."""
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected")
            return None
        game_version = self.getShortGameName(game_path).lower()
        meta = self.main_data_manager.getDbMeta(game_version, squad_type)
        table_data = meta.get(table_name)
        return [field["name"] for field in table_data["fields"]] if table_data else None
    
    def getInstalledCurrentTitleUpdate(self, config_mgr: ConfigManager) -> Optional[Dict[str, Any]]:
        if not (game_path := config_mgr.getConfigKeySelectedGame()): return None
        content = self.loadGameContent(game_path, config_mgr=config_mgr)
        return next((u for u in content.get(self.getProfileTypeTitleUpdate(), {}).get(self.getContentKeyTitleUpdate(), []) if u.get(self.getTitleUpdateSHA1Key()) == config_mgr.getConfigKeySHA1()), None)
        
    def getSelectedUpdate(self, tab_key: str, table_component) -> Optional[str]:
        if table_component and hasattr(table_component, 'table') and (selected := table_component.table.selectedIndexes()):
            name_key = self.getTitleUpdateNameKey() if tab_key == self.getTabKeyTitleUpdates() else self.getSquadsNameKey() if tab_key == self.getTabKeySquadsUpdates() else self.getFutSquadsNameKey()
            return table_component.table.item(selected[0].row(), 0).text()
        return None
    
    def getGameSettingsFolderPath(self, game_path: str) -> str:
        if game_path:
            base_path = self.GAME_PATHS.get(self.getShortGameName(game_path), {}).get("SettingsBase")
        return os.path.join(base_path, "settings") if base_path else ""

    def getLiveTuningUpdateFilePath(self, game_path: str) -> str:
        if game_path:
            base_path = self.GAME_PATHS.get(self.getShortGameName(game_path), {}).get("LiveTuningBase")
        return os.path.join(base_path, "onlinecache0", "attribdb.bin") if base_path else ""
    
    def getProfileTypeTitleUpdate(self) -> str: return self._profile_types[0]
    def getProfileTypeSquad(self) -> str: return self._profile_types[1]
    def getProfileTypes(self) -> List[str]: return self._profile_types.copy()
    def getContentKeyTitleUpdate(self) -> str: return self._content_keys[0]
    def getContentKeySquad(self) -> str: return self._content_keys[1]
    def getContentKeyFutSquad(self) -> str: return self._content_keys[2]
    def getContentKeys(self) -> List[str]: return self._content_keys.copy()
    def getTabKeyTitleUpdates(self) -> str: return "TitleUpdates"
    def getTabKeySquadsUpdates(self) -> str: return "SquadsUpdates"
    def getTabKeyFutSquadsUpdates(self) -> str: return "FutSquadsUpdates"
    def getTabKeys(self) -> List[str]: return [self.getTabKeyTitleUpdates(), self.getTabKeySquadsUpdates(), self.getTabKeyFutSquadsUpdates()]
    def getAvailableColumnsForTable(self, tab_key: str) -> List[str]:
        columns = self._get_base_columns(tab_key)
        return [col for col in columns if col not in self.excluded_column_keys]
    
    def getColumnOrderForTable(self, tab_key: str) -> List[str]:
        return [col for col in self._get_base_columns(tab_key) if col not in self.excluded_column_keys]

    def _get_base_columns(self, tab_key: str) -> List[str]:
        if tab_key == self.getTabKeyTitleUpdates(): return self.title_updates_keys
        elif tab_key == self.getTabKeySquadsUpdates(): return self.squads_keys
        elif tab_key == self.getTabKeyFutSquadsUpdates(): return self.fut_squads_keys
        return []
    
    def getGameProfile(self, version: str, profile_type: str = None) -> Dict[str, str]:
        profile_type = profile_type or self.getProfileTypeTitleUpdate()
        if profile_type not in self._profile_types:
            raise KeyError(f"Profile type '{profile_type}' not found")
        return {"exe_name": f"{self.GAME_PREFIX}{version}.exe", "registry_key": rf"SOFTWARE\{self.GAME_PUBLISHER_NAME}\{self.GAME_PUBLISHER_NAME} {self.GAME_PREFIX} {version}", "manifest_url": f"{self.profiles_base_url}{self.GAME_PREFIX}{version}/{profile_type}.json", "SHORT_GAME_NAME": f"{self.GAME_PREFIX}{version}"}
    
    def getProfileByShortName(self, SHORT_GAME_NAME: str, profile_type: str = None) -> Dict[str, str]:
        profile_type = profile_type or self.getProfileTypeTitleUpdate()
        if profile_type not in self._profile_types or SHORT_GAME_NAME.replace(self.GAME_PREFIX, "") not in self.GAME_VERSION:
            ErrorHandler.handleError(f"Invalid profile_type '{profile_type}' or SHORT_GAME_NAME '{SHORT_GAME_NAME}'")
            return {}
        return self.getGameProfile(SHORT_GAME_NAME.replace(self.GAME_PREFIX, ""), profile_type)
    
    def getGamesFromRegistry(self, emit_status: Optional[Callable[[str], None]] = None, is_rescan: bool = False) -> Dict[str, str]:
        valid_paths = {}
        if emit_status and is_rescan: emit_status([("Rescanning for games...", "white")])
        for version in self.GAME_VERSION:
            profile = self.getGameProfile(version)
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, profile["registry_key"]) as key:
                    install_dir, _ = winreg.QueryValueEx(key, "Install Dir")
                    game_path = os.path.join(install_dir, profile["exe_name"])
                    if os.path.exists(game_path):
                        valid_paths[profile["exe_name"]] = game_path
                        logger.info(f"Game found: {profile['exe_name']}")
            except FileNotFoundError:
                logger.info(f"Registry key not found for: {profile['exe_name']}")
            except Exception as e:
                ErrorHandler.handleError(f"Error accessing registry for {profile['exe_name']}: {e}")
        return valid_paths
    
    def getShortGameName(self, path: str) -> str:
        if not path:
            logger.warning(f"Empty game path provided, returning empty string\nCall stack:\n{''.join(traceback.format_stack(limit=5)[:-1])}")
            return ""
        if not os.path.exists(path):
            logger.warning(f"Game path does not exist: {path}")
            return ""
        return os.path.basename(path.strip("\\/")).replace(f"{self.GAME_PUBLISHER_NAME}", "").replace(" ", "")
    
    def getProfileDirectory(self, SHORT_GAME_NAME: str, subfolder: str) -> str:
        if not SHORT_GAME_NAME or not subfolder:
            raise ValueError("SHORT_GAME_NAME and subfolder must be non-empty strings")
        cache_key = f"{SHORT_GAME_NAME}_{subfolder}"
        if cache_key not in self._profile_dir_cache:
            profile_dir = os.path.join(os.getcwd(), self.PROFILES_DIR, SHORT_GAME_NAME, subfolder)
            os.makedirs(profile_dir, exist_ok=True)
            if subfolder == self.getProfileTypeSquad():
                squads_dir = os.path.join(profile_dir, self.getContentKeySquad())
                fut_squads_dir = os.path.join(profile_dir, self.getContentKeyFutSquad())
                os.makedirs(squads_dir, exist_ok=True)
                os.makedirs(fut_squads_dir, exist_ok=True)
                logger.debug(f"Created Squads subdirectories: {squads_dir}, {fut_squads_dir}")
            self._profile_dir_cache[cache_key] = profile_dir
            logger.debug(f"Profile directory initialized: {profile_dir}")
        return self._profile_dir_cache[cache_key]
    
    def getUpdatesList(self, content: Dict[str, Any], SHORT_GAME_NAME: str, profile_type: str = None) -> Dict[str, List[Dict[str, Any]]]:
        profile_type = profile_type or self.getProfileTypeTitleUpdate()
        return {self.getContentKeyTitleUpdate(): content.get(self.getContentKeyTitleUpdate(), [])} if profile_type == self.getProfileTypeTitleUpdate() else {self.getContentKeySquad(): content.get(self.getContentKeySquad(), []), self.getContentKeyFutSquad(): content.get(self.getContentKeyFutSquad(), [])}
    
    def calculateSHA1(self, input_data: str, is_file: bool = True) -> Optional[str]:
        try:
            sha1 = hashlib.sha1()
            if is_file:
                with open(input_data, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        sha1.update(chunk)
            else:
                sha1.update(input_data)
            return sha1.hexdigest()
        except Exception as e:
            ErrorHandler.handleError(f"Error calculate SHA1: {e}")
            return None
    
    def validateAndUpdateGameExeSHA1(self, path: str, config_mgr: ConfigManager) -> bool:
        if not path or not os.path.exists(path):
            logger.info("No selected game.")
            return False
        
        old_sha1 = config_mgr.getConfigKeySHA1()
        for version in self.GAME_VERSION:
            profile = self.getGameProfile(version)
            exe_path = os.path.join(path, profile["exe_name"])
            if os.path.exists(exe_path):
                new_sha1 = self.calculateSHA1(exe_path)
                if not new_sha1:
                    return False
                if old_sha1 != new_sha1:
                    config_mgr.setConfigKeySHA1(new_sha1)
                    logger.info(f"SHA1 {'updated' if old_sha1 else 'calculated'}: {new_sha1}")
                return True
        logger.warning("No valid executable found")
        return False
    
    def loadGameContent(self, path: str, emit_status: Optional[Callable[[str], None]] = None, config_mgr: Optional[ConfigManager] = None) -> Dict[str, Any]:
        if not self.getShortGameName(path):
            ErrorHandler.handleError(f"Could not determine game name from path: {path}")
            return {}
        if "demo" in path.lower() or "trial" in path.lower():
            ErrorHandler.handleError("Failed to load game content:\nIt seems like your game is a demo or trial version, which we do not support. Please make sure you have the full version of the game to proceed.")
            return {}
        local_file = os.path.join(self.app_data_manager.getDataFolder(), f"{self.getShortGameName(path)}.cache")
        if not os.path.exists(local_file):
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
        base_cache_file = os.path.join(MainDataManager().getBaseCache(), f"{self.getShortGameName(path)}.cache")
        all_profile_types = self.getProfileTypes()
        if all(f"{self.getShortGameName(path)}_{pt}" in self._content_cache for pt in all_profile_types):
            if emit_status: emit_status([("Loading locally cached content ", "white"), ("(Up to date)", "#00FF00")])
            return {pt: self._content_cache[f"{self.getShortGameName(path)}_{pt}"] for pt in all_profile_types}
        content = self._load_local_cache(local_file, emit_status)
        if not content and os.path.exists(local_file):
            updated_content = self._fetch_updates(self.getShortGameName(path), all_profile_types, emit_status)
            if updated_content: content = self._update_cache(local_file, {}, updated_content, emit_status)
            else: content = self._load_base_cache(base_cache_file, self.getShortGameName(path), emit_status)
        elif not content and not os.path.exists(local_file):
            updated_content = self._fetch_updates(self.getShortGameName(path), all_profile_types, emit_status)
            if updated_content: content = self._update_cache(local_file, {}, updated_content, emit_status)
            else: content = self._load_base_cache(base_cache_file, self.getShortGameName(path), emit_status)
        elif content:
            updated_content = self._fetch_updates(self.getShortGameName(path), all_profile_types, emit_status)
            if updated_content: content = self._update_cache(local_file, content, updated_content, emit_status)
            elif emit_status: emit_status([("Loading locally cached content ", "white"), ("(Offline mode)", "red")])
        if not content:
            ErrorHandler.handleError(f"Failed to load game content for {self.getShortGameName(path)} despite all fallback attempts.\nPlease check your internet connection to retrieve the latest updates and try again.")
            return {}
        return content
    
    def _load_base_cache(self, base_cache_file: str, SHORT_GAME_NAME: str, emit_status: Optional[Callable[[str], None]]) -> Dict[str, Any]:
        content = {}
        if os.path.exists(base_cache_file):
            if emit_status: emit_status([("Loading BaseCache as fallback ", "white"), ("(Out of date)", "red")])
            try:
                with open(base_cache_file, "rb") as f:
                    content = pickle.loads(zlib.decompress(f.read()))
                self._content_cache.update({f"{SHORT_GAME_NAME}_{k}": v for k, v in content.items()})
                logger.info(f"Loaded BaseCache for {SHORT_GAME_NAME} from {base_cache_file}")
                NotificationHandler.showWarning("The tool couldn’t fetch the latest list updates, and no recent local cache is available/valid to load.\n\nWe’ve switched to a base data list, meaning the lists are most likely out of date!, Please check your internet connection to retrieve the latest updates when possible.\n\nClick OK to continue.")
            except Exception as e:
                logger.error(f"Failed to load BaseCache {base_cache_file}: {e}")
        else:
            logger.warning(f"BaseCache file not found at {base_cache_file}")
        return content
    
    def _load_local_cache(self, local_file: str, emit_status: Optional[Callable[[str], None]]) -> Dict[str, Any]:
        content = {}
        if os.path.exists(local_file):
            if emit_status: emit_status([("Loading locally cached content", "white")])
            try:
                with open(local_file, "rb") as f:
                    content = pickle.loads(zlib.decompress(f.read()))
                self._content_cache.update({f"{os.path.splitext(os.path.basename(local_file))[0]}_{k}": v for k, v in content.items()})
                logger.info(f"Cache loaded for {os.path.splitext(os.path.basename(local_file))[0]} from {local_file}")
            except Exception as e:
                logger.error(f"Failed to load local cache {local_file}: {e}")
        return content
    
    def _fetch_updates(self, SHORT_GAME_NAME: str, profile_types: List[str], emit_status: Optional[Callable[[str], None]]) -> Dict[str, Any]:
        if emit_status: emit_status([("Checking for new updates...", "white")])
        updated_content = {}
        fetch_failed = False
        for p_type in profile_types:
            profile = self.getGameProfile(SHORT_GAME_NAME.replace(self.GAME_PREFIX, ""), p_type)
            for attempt in range(self.MAX_RETRIES):
                try:
                    response = requests.get(profile["manifest_url"], timeout=self.TIMEOUT)
                    response.raise_for_status()
                    updated_content[p_type] = response.json()
                    logger.debug(f"Fetched content for {SHORT_GAME_NAME}_{p_type}")
                    break
                except requests.RequestException as e:
                    logger.error(f"Attempt {attempt + 1} failed for {profile['manifest_url']}: {e}")
                    if attempt == self.MAX_RETRIES - 1:
                        logger.error(f"Failed to fetch {profile['manifest_url']} after {self.MAX_RETRIES} attempts")
                        fetch_failed = True
                        break
        self.is_offline = fetch_failed
        return updated_content if not fetch_failed else {}

    def _get_content_version(self, updated_content: Dict[str, Any], content: Dict[str, Any], tab_key: str) -> str:
        """Get the content version for a given tab based on display settings."""
        config_mgr = ConfigManager()
        display_type = config_mgr.getConfigKeyContentVersionDisplay(tab_key)
        version_key = {
            'TitleUpdates': 'ContentVersion' if display_type == 'VersionByNumber' else 'ContentVersionDate',
            'SquadsUpdates': 'SquadsContentVersion' if display_type == 'VersionByNumber' else 'SquadsContentVersionDate',
            'FutSquadsUpdates': 'FutSquadsContentVersion' if display_type == 'VersionByNumber' else 'FutSquadsContentVersionDate'
        }.get(tab_key, 'ContentVersion')
        profile_type = self.getProfileTypeTitleUpdate() if tab_key == self.getTabKeyTitleUpdates() else self.getProfileTypeSquad()
        return (updated_content or content).get(profile_type, {}).get(version_key, 'N/A')

    def _update_cache(self, local_file: str, content: Dict[str, Any], updated_content: Dict[str, Any], emit_status: Optional[Callable[[str], None]]) -> Dict[str, Any]:
        if updated_content:
            local_bytes = zlib.compress(pickle.dumps(content))
            updated_bytes = zlib.compress(pickle.dumps(updated_content))
            if os.path.exists(local_file):
                if self.calculateSHA1(local_bytes, is_file=False) != self.calculateSHA1(updated_bytes, is_file=False):
                    if emit_status: emit_status([("New Update Detected", "#00FF00"), ("<br>Re-Building local cache...", "white")])
                    content = updated_content
                    with open(local_file, "wb") as f: f.write(updated_bytes)
                    self._content_cache.update({f"{os.path.splitext(os.path.basename(local_file))[0]}_{k}": v for k, v in content.items()})
                    logger.info(f"Updated local cache file at {local_file}")
                else:
                    logger.info(f"Lists are up to date. TitleUpdatesContentVersion: {self._get_content_version(updated_content, content, 'TitleUpdates')}, "
            f"SquadsContentVersion: {self._get_content_version(updated_content, content, 'SquadsUpdates')}, "
            f"FutSquadsContentVersion: {self._get_content_version(updated_content, content, 'FutSquadsUpdates')}")
                    if emit_status: emit_status([("Loading locally cached content ", "white"), ("(Up to date)", "#00FF00")])
            else:
                if emit_status: emit_status([("Building local cache...", "white")])
                content = updated_content
                with open(local_file, "wb") as f: f.write(updated_bytes)
                self._content_cache.update({f"{os.path.splitext(os.path.basename(local_file))[0]}_{k}": v for k, v in content.items()})
                logger.info(f"Created local cache file at {local_file}")
        elif content:
            if emit_status: emit_status([("Loading locally cached content ", "white"), ("(Offline mode)", "red")])
            logger.warning(f"Using local cache in Offline mode for {os.path.splitext(os.path.basename(local_file))[0]}")
            NotificationHandler.showWarning("The tool couldn’t verify content updates or failed to check for content updates.\n\nWe’ll use the last updated local cache, which might be out of date! Please check your internet connection to retrieve the latest updates when possible.\n\nClick OK to continue.")
        else:
            logger.error(f"Failed to fetch updates and no valid local cache available for {os.path.splitext(os.path.basename(local_file))[0]}")
            return {}
        return content
    
    def getLiveEditorVersionsUrl(self, game_version: str) -> str:
        """Get the live editor version.json URL based on the game version."""
        return f"https://raw.githubusercontent.com/xAranaktu/{self.GAME_PREFIX}-{game_version}-Live-Editor/main/version.json"
    def fetchLiveEditorVersionsData(self, config_mgr: ConfigManager) -> Optional[Dict]:
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected")
            return None
        url = self.getLiveEditorVersionsUrl(self.getShortGameName(game_path).replace(self.GAME_PREFIX, ""))
        if url in self._live_editor_versions_cache:
            return self._live_editor_versions_cache[url]
        try:
            r = requests.get(url, timeout=self.TIMEOUT)
            r.raise_for_status()
            self._live_editor_versions_cache[url] = data = r.json()
            return data
        except requests.RequestException as e:
            ErrorHandler.handleError(f"Failed to fetch live editor version.json from {url}: {e}")
            return None
    def getLiveEditorGameVer(self, config_mgr: ConfigManager) -> Optional[Dict]:
        return (data := self.fetchLiveEditorVersionsData(config_mgr)) and data.get("game_ver", {})
    def getLiveEditorLeVersions(self, config_mgr: ConfigManager) -> Optional[Dict]:
        return (data := self.fetchLiveEditorVersionsData(config_mgr)) and data.get("le_ver", {})
    def getLiveEditorCompatibility(self, config_mgr: ConfigManager) -> Optional[Dict]:
        return (data := self.fetchLiveEditorVersionsData(config_mgr)) and data.get("compatibility", {})
    
    def getGameSemVer(self, config_mgr: ConfigManager) -> Optional[str]:
        """Get game SemVer from installerdata.xml."""
        if not (game_path := config_mgr.getConfigKeySelectedGame()): return None
        xml_path = os.path.join(game_path, "__Installer", "installerdata.xml")
        try:
            return ET.parse(xml_path).find(".//gameVersion").attrib["version"]
        except (FileNotFoundError, ET.ParseError, AttributeError) as e:
            ErrorHandler.handleError(f"Failed to get SemVer: {e}")
            return None

    def getLiveEditorVersion(self, config_mgr: ConfigManager) -> Optional[str]:
        """Get Live Editor version from changelog.txt via registry."""
        if not (game_path := config_mgr.getConfigKeySelectedGame()): return None
        game_version = self.getShortGameName(game_path).replace(self.GAME_PREFIX, "")
        reg_path = f"SOFTWARE\\Live Editor\\{self.GAME_PREFIX} {game_version}"
        key_name = "Data Dir" if game_version == "24" else "Install Dir"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                dir_path = winreg.QueryValueEx(key, key_name)[0]
            for file_name in os.listdir(dir_path):
                if "changelog" in file_name.lower():
                    file_path = os.path.join(dir_path, file_name)
                    with open(file_path, "r", encoding="utf-8") as f:
                        if match := re.match(r"v\d+\.\d+\.\d+", f.read()):
                            return match.group(0)
        except (WindowsError, FileNotFoundError, re.error) as e:
            ErrorHandler.handleError(f"Failed to get Live Editor version: {e}")
            return None
    
class AppDataManager:
    TEMP_ROOT = os.getenv('LOCALAPPDATA')
    TEMP_DIR = os.path.join(TEMP_ROOT, "FC_Rollback_Tool", "Temp")
    DATA_DIR = os.path.join(TEMP_ROOT, "FC_Rollback_Tool", "Data")
    BACKUPS_DIR = os.path.join(TEMP_ROOT, "FC_Rollback_Tool", "Data", "Backups")
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUPS_DIR, exist_ok=True)

    @staticmethod
    def getTempFolder() -> str: return AppDataManager.TEMP_DIR
    @staticmethod
    def getDataFolder() -> str: return AppDataManager.DATA_DIR
    @staticmethod
    def getBackupsFolder() -> str: return AppDataManager.BACKUPS_DIR

    @staticmethod
    def manageTempFolder(clean: bool = False, subfolder: str = None, clean_all: bool = False) -> Optional[str]:
        try:
            if clean_all and os.path.exists(AppDataManager.TEMP_DIR):
                shutil.rmtree(AppDataManager.TEMP_DIR, ignore_errors=True)
                logger.info(f"Temp folder fully cleaned: {AppDataManager.TEMP_DIR}")
            elif clean and subfolder:
                subfolder_path = os.path.join(AppDataManager.TEMP_DIR, subfolder)
                if os.path.exists(subfolder_path):
                    shutil.rmtree(subfolder_path, ignore_errors=True)
                    logger.info(f"Temp subfolder cleaned: {subfolder_path}")
            if not os.path.exists(AppDataManager.TEMP_DIR):
                os.makedirs(AppDataManager.TEMP_DIR, exist_ok=True)
            return AppDataManager.TEMP_DIR
        except Exception as e:
            ErrorHandler.handleError(f"Error handling temp folder: {e}")
            return None

class NotificationHandler:
    INFO_TITLE = "FC Rollback Tool - Information"
    WARNING_TITLE = "FC Rollback Tool - Warning"
    CONFIRM_TITLE = "FC Rollback Tool - Confirmation"

    @staticmethod
    def showInfo(message: str) -> None:
        logger.info(message)
        win32api.MessageBox(0, message, NotificationHandler.INFO_TITLE, win32con.MB_OK | win32con.MB_ICONINFORMATION)

    @staticmethod
    def showWarning(message: str) -> None:
        logger.warning(message)
        win32api.MessageBox(0, message, NotificationHandler.WARNING_TITLE, win32con.MB_OK | win32con.MB_ICONWARNING)

    @staticmethod
    def showConfirmation(message: str) -> str:
        response = win32api.MessageBox(0, message, NotificationHandler.CONFIRM_TITLE, win32con.MB_YESNOCANCEL | win32con.MB_ICONQUESTION)
        if response == win32con.IDYES:
            return "Yes"
        elif response == win32con.IDNO:
            return "No"
        return "Cancel"

class ErrorHandler:
    ERR_TITLE = "FC Rollback Tool - Error"

    @staticmethod
    def handleError(message: str) -> None:
        logger.error(message)
        win32api.MessageBox(0, message, ErrorHandler.ERR_TITLE, win32con.MB_OK | win32con.MB_ICONERROR)