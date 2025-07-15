import os
import re
import winreg
import hashlib
import requests
import pickle
import zlib
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
import xml.etree.ElementTree as ET

from Core.Logger import logger
from Core.ToolUpdateManager import GITHUB_ACC, GITHUB_ACC_TOOL, UPDATES_REPO
from Core.MainDataManager import MainDataManager
from Core.ConfigManager import ConfigManager
from Core.AppDataManager import AppDataManager
from Core.NotificationManager import NotificationHandler
from Core.ErrorHandler import ErrorHandler

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
        self.title_updates_keys = ["ContentVersion", "ContentVersionDate", "AppID", "MainDepotID", "eng_usDepotID", "Name", "SemVer", "PatchID", "ReleasedDate", "RelativeDate", "Size", "MainManifestID", "eng_usManifestID", "PatchNotes", "SHA1", "DownloadURL"]
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
        match = re.search(rf"{self.GAME_PREFIX}\s*(\d+)", path, re.IGNORECASE)
        if match:
            return f"{self.GAME_PREFIX}{match.group(1)}"
        logger.warning(f"Could not extract game version from path: {path}")
        return ""
    
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
        installerdata_path = os.path.join(game_path, "__Installer", "installerdata.xml")
        try:
            return ET.parse(installerdata_path).find(".//gameVersion").attrib["version"]
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
        
    def getPatchVersion(self, game_path: str) -> Optional[tuple]:
        """Get patch version from layout.toc"""
        layout_toc_path = os.path.join(game_path, "Patch", "layout.toc")
        try:
            with open(layout_toc_path, "rb") as f:
                data = f.read()
                pos = data.find(b"head\x00") + 5
                return (int.from_bytes(data[pos:pos+4], "little"), data[pos:pos+4].hex()) if pos + 4 <= len(data) else (None, None)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to get Patch Version: {e}")
            return None