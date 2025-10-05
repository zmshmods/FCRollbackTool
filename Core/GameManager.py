import os
import re
import json
import winreg
import hashlib
import requests
import pickle
import zlib
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
from Core.GameProfile import GameProfileManager, GameProfile

try:
    from Core.FIFAModMetaReader import ModReaderFactory # type: ignore
except ModuleNotFoundError:
    ModReaderFactory = None
    logger.warning("Core.FIFAModMetaReader module not available in the source code.")

from Libraries.SteamDDLib.app.manifest_parser import Manifest

class GameManager:
    def __init__(self):
        self.profile_manager = GameProfileManager()
        self.PROFILES_DIR = "Profiles"
        self.TIMEOUT = 7
        self.MAX_RETRIES = 2
        
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
        self.main_data_manager = MainDataManager()
        os.makedirs(self.app_data_manager.getDataFolder(), exist_ok=True)
        self._index_cache = {}
        self._live_editor_versions_cache = {}
        self._mods_cache = {}
        self._depot_manifest_cache = {}
        self._depot_changelog_cache = {}

    # region Getters for Keys and Constants
    def getTitleUpdateSHA1Key(self) -> str: return "SHA1"
    def getTitleUpdateContentVersionKey(self) -> str: return "ContentVersion"
    def getTitleUpdateContentVersionDateKey(self) -> str: return "ContentVersionDate"
    def getTitleUpdateAppIDKey(self) -> str: return "AppID"
    def getTitleUpdateMainDepotIDKey(self) -> str: return "MainDepotID"
    def getTitleUpdateEngUsDepotIDKey(self) -> str: return "eng_usDepotID"
    def getTitleUpdateNameKey(self) -> str: return "Name"
    def getTitleUpdateSemVerKey(self) -> str: return "SemVer"
    def getTitleUpdatePatchIDKey(self) -> str: return "PatchID"
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
    
    def getDbExtension(self) -> str: return ".db"
    def getTableExtension(self) -> str: return ".csv"
    def getChangelogsExtension(self) -> str: return ".xlsx"
    
    def getProfileTypeTitleUpdate(self) -> str: return "TitleUpdates"
    def getProfileTypeSquad(self) -> str: return "SquadsUpdates"
    def getProfileTypes(self) -> List[str]: return [self.getProfileTypeTitleUpdate(), self.getProfileTypeSquad()]
    def getContentKeyTitleUpdate(self) -> str: return self._content_keys[0]
    def getContentKeySquad(self) -> str: return self._content_keys[1]
    def getContentKeyFutSquad(self) -> str: return self._content_keys[2]
    def getContentKeys(self) -> List[str]: return self._content_keys.copy()
    def getTabKeyTitleUpdates(self) -> str: return "TitleUpdates"
    def getTabKeySquadsUpdates(self) -> str: return "SquadsUpdates"
    def getTabKeyFutSquadsUpdates(self) -> str: return "FutSquadsUpdates"
    def getTabKeys(self) -> List[str]: return [self.getTabKeyTitleUpdates(), self.getTabKeySquadsUpdates(), self.getTabKeyFutSquadsUpdates()]
    
    def getDownloadURLKeyForTab(self, tab_key: str) -> str:
        if tab_key == self.getTabKeyTitleUpdates(): return self.getTitleUpdateDownloadURLKey()
        elif tab_key == self.getTabKeySquadsUpdates(): return self.getSquadsDownloadURLKey()
        elif tab_key == self.getTabKeyFutSquadsUpdates(): return self.getFutSquadsDownloadURLKey()
        raise ValueError(f"Invalid tab_key: {tab_key}")

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
    # endregion

    # region Game and Path Management
    def _get_profile(self, game_root_path: str) -> Optional[GameProfile]:
        if not game_root_path or not os.path.isdir(game_root_path):
            logger.warning(f"Invalid game root path provided: {game_root_path}")
            return None
        return self.profile_manager.get_profile_by_exe(os.path.basename(game_root_path))

    def getGamesFromRegistry(self, emit_status: Optional[Callable[[str], None]] = None, is_rescan: bool = False) -> Dict[str, str]:
        valid_paths = {}
        if emit_status and is_rescan: emit_status([("Rescanning for games...", "white")])
        for profile in self.profile_manager.get_all_profiles():
            keys_to_check = profile.registry_key if isinstance(profile.registry_key, list) else [profile.registry_key]
            
            found_game_for_profile = False

            for key_path in keys_to_check:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                        install_dir, _ = winreg.QueryValueEx(key, profile.registry_value_name)
                        install_dir = os.path.normpath(install_dir)
                        game_path = os.path.join(install_dir, profile.exe_name)
                        if os.path.exists(game_path):
                            valid_paths[profile.exe_name] = install_dir
                            logger.info(f"Game found: {profile.exe_name}")
                            
                            found_game_for_profile = True
                            break
                except FileNotFoundError:
                    continue
                except Exception as e:
                    ErrorHandler.handleError(f"Error accessing registry for {profile.exe_name} at {key_path}: {e}")

            if not found_game_for_profile:
                logger.info(f"Game not found in registry path for: {profile.exe_name}")

        manual_paths = ConfigManager().getConfigKeyManuallyAddedGames()
        for path in manual_paths:
            if not os.path.isdir(path):
                continue
            for profile in self.profile_manager.get_all_profiles():
                exe_path = os.path.join(path, profile.exe_name)
                if os.path.exists(exe_path):
                    if profile.exe_name not in valid_paths:
                        valid_paths[profile.exe_name] = path
                        logger.info(f"Manually added game found: {profile.exe_name}")
                    break
                
        return valid_paths

    def getSelectedGameId(self, game_root_path: str) -> str:
        profile = self._get_profile(game_root_path)
        return profile.id if profile else ""
    
    def getGameSettingsFolderPath(self, game_root_path: str) -> str:
        profile = self._get_profile(game_root_path)
        return profile.settings_path if profile else ""

    def getLiveTuningUpdateFilePath(self, game_root_path: str) -> str:
        profile = self._get_profile(game_root_path)
        return profile.live_tuning_path if profile else ""
        
    def getProfileDirectory(self, game_id: str, subfolder: str) -> str:
        if not game_id or not subfolder:
            raise ValueError("game_id and subfolder must be non-empty strings")
        
        top_level_subfolder = subfolder.split(os.sep)[0]
        
        profile = self.profile_manager.get_profile(game_id)
        if not profile or top_level_subfolder not in profile.supported_profiles:
             raise ValueError(f"Invalid game_id '{game_id}' or subfolder '{subfolder}'")
             
        cache_key = f"{game_id}_{subfolder}"
        if cache_key not in self._profile_dir_cache:
            profile_dir = os.path.join(os.getcwd(), self.PROFILES_DIR, game_id, subfolder)
            os.makedirs(profile_dir, exist_ok=True)
            self._profile_dir_cache[cache_key] = profile_dir
            logger.debug(f"Profile directory initialized: {profile_dir}")
        return self._profile_dir_cache[cache_key]
    
    def _get_profile_from_config(self, config_mgr: ConfigManager) -> Optional[GameProfile]:
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected")
            return None
        return self._get_profile(game_path)
    # endregion

    # region Data Fetching and Caching
    def loadGameContent(self, path: str, emit_status: Optional[Callable[[str], None]] = None, config_mgr: Optional[ConfigManager] = None) -> Dict[str, Any]:
        profile = self._get_profile(path)
        if not profile:
            ErrorHandler.handleError(f"Could not determine game profile from path: {path}")
            return {}
            
        game_id = profile.id
        if "demo" in path.lower() or "trial" in path.lower():
            ErrorHandler.handleError("Failed to load game content:\nIt seems like your game is a demo or trial version, which we do not support. Please make sure you have the full version of the game to proceed.")
            return {}
        
        local_file = os.path.join(self.app_data_manager.getDataFolder(), f"{game_id}.cache")
        os.makedirs(os.path.dirname(local_file), exist_ok=True)

        base_cache_file = os.path.join(MainDataManager().getBaseCache(), f"{game_id}.cache")
        
        all_profile_types = profile.supported_profiles

        if all(f"{game_id}_{pt}" in self._content_cache for pt in all_profile_types):
            if emit_status: emit_status([("Loading locally cached content ", "white"), ("(Up to date)", "#00FF00")])
            return {pt: self._content_cache[f"{game_id}_{pt}"] for pt in all_profile_types}

        content = self._load_local_cache(local_file, emit_status)
        if not content and os.path.exists(local_file):
            updated_content = self._fetch_updates(game_id, all_profile_types, emit_status)
            if updated_content: content = self._update_cache(local_file, {}, updated_content, emit_status)
            else: content = self._load_base_cache(base_cache_file, game_id, emit_status)
        elif not content and not os.path.exists(local_file):
            updated_content = self._fetch_updates(game_id, all_profile_types, emit_status)
            if updated_content: content = self._update_cache(local_file, {}, updated_content, emit_status)
            else: content = self._load_base_cache(base_cache_file, game_id, emit_status)
        elif content:
            updated_content = self._fetch_updates(game_id, all_profile_types, emit_status)
            if updated_content: content = self._update_cache(local_file, content, updated_content, emit_status)
            elif emit_status: emit_status([("Loading locally cached content ", "white"), ("(Offline mode)", "red")])
        
        if not content:
            ErrorHandler.handleError(f"Failed to load game content for {game_id} despite all fallback attempts.\nPlease check your internet connection to retrieve the latest updates and try again.")
            return {}
        return content
    
    def _load_base_cache(self, base_cache_file: str, game_id: str, emit_status: Optional[Callable[[str], None]]) -> Dict[str, Any]:
        content = {}
        if os.path.exists(base_cache_file):
            if emit_status: emit_status([("Loading BaseCache as fallback ", "white"), ("(Out of date)", "red")])
            try:
                with open(base_cache_file, "rb") as f:
                    content = pickle.loads(zlib.decompress(f.read()))
                self._content_cache.update({f"{game_id}_{k}": v for k, v in content.items()})
                logger.info(f"Loaded BaseCache for {game_id} from {base_cache_file}")
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
    
    def _fetch_updates(self, game_id: str, profile_types: List[str], emit_status: Optional[Callable[[str], None]]) -> Dict[str, Any]:
        if emit_status: emit_status([("Checking for new updates...", "white")])
        updated_content = {}
        fetch_failed = False
        for p_type in profile_types:
            manifest_url = f"{self.profiles_base_url}{game_id}/{p_type}.json"
            for attempt in range(self.MAX_RETRIES):
                try:
                    response = requests.get(manifest_url, timeout=self.TIMEOUT)
                    response.raise_for_status()
                    updated_content[p_type] = response.json()
                    logger.debug(f"Fetched content for {game_id}_{p_type}")
                    break
                except requests.RequestException as e:
                    logger.error(f"Attempt {attempt + 1} failed for {manifest_url}: {e}")
                    if attempt == self.MAX_RETRIES - 1:
                        logger.error(f"Failed to fetch {manifest_url} after {self.MAX_RETRIES} attempts")
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
    # endregion

    # region Squads and DB Data
    def getUpdatesList(self, content: Dict[str, Any], profile_type: str = None) -> Dict[str, List[Dict[str, Any]]]:
        profile_type = profile_type or self.getProfileTypeTitleUpdate()
        return {self.getContentKeyTitleUpdate(): content.get(self.getContentKeyTitleUpdate(), [])} if profile_type == self.getProfileTypeTitleUpdate() else {self.getContentKeySquad(): content.get(self.getContentKeySquad(), []), self.getContentKeyFutSquad(): content.get(self.getContentKeyFutSquad(), [])}
        
    def getSquadsBaseURL(self, game_version: str) -> str:
        """Get the squads base URL based on the game version."""
        return f"https://raw.githubusercontent.com/{GITHUB_ACC_TOOL}/FC{game_version}Squads/main"

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

    def _get_profile(self, game_root_path: str) -> Optional[GameProfile]:
        if not game_root_path or not os.path.isdir(game_root_path):
            logger.warning(f"Invalid game root path provided: {game_root_path}")
            return None
        
        for profile in self.profile_manager.get_all_profiles():
            if os.path.exists(os.path.join(game_root_path, profile.exe_name)):
                return profile
                
        logger.warning(f"Could not determine game profile from path: {game_root_path}")
        return None

    def getTableUrl(self, index_url: str, table_name: str, config_mgr: ConfigManager) -> Optional[str]:
        """Get the full URL for a specific table based on the selected game."""
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None

        tables_path = self.getTablesPath(index_url)
        if not tables_path:
            return None
        return f"{self.getSquadsBaseURL(profile.version)}/{tables_path}/{table_name}{self.getTableExtension()}"

    def getChangelogUrl(self, index_url: str, changelog_name: str, config_mgr: ConfigManager) -> Optional[str]:
        """Get the full URL for a specific changelog based on the selected game."""
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None

        changelogs_path = self.getChangelogsPath(index_url)
        if not changelogs_path:
            return None
        clean_changelog_name = changelog_name.replace(self.getChangelogsExtension(), "")
        return f"{self.getSquadsBaseURL(profile.version)}/{changelogs_path}/{clean_changelog_name}{self.getChangelogsExtension()}"

    def getSquadFilePathKey(self, index_url: str, config_mgr: ConfigManager) -> Optional[str]:
        """Fetch and construct full SquadFilePath URL from Index.json."""
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None
        
        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        squad_file_path = index_data.get("SquadFilePath")
        if not squad_file_path:
            ErrorHandler.handleError(f"SquadFilePath not found in Index.json: {index_url}")
            return None
        return f"{self.getSquadsBaseURL(profile.version)}/{squad_file_path}"

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
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None

        index_data = self.fetchIndexData(index_url)
        if not index_data:
            return None
        db_path = index_data.get("Databases", [{}])[0].get("DbPath")
        if not db_path:
            ErrorHandler.handleError(f"DbPath not found in Index.json: {index_url}")
            return None
        return f"{self.getSquadsBaseURL(profile.version)}/{db_path}"

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
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None

        tables_path = self.getTablesPath(index_url)
        if not tables_path:
            return None
        full_path = f"{self.getSquadsBaseURL(profile.version)}/{tables_path}"
        if table_name:
            full_path = f"{full_path}/{table_name}{self.getTableExtension()}"
        return full_path

    def getSquadTypeFromIndexUrl(self, index_url: str) -> str:
        if "FutSquads" in index_url:
            return "FutSquads"
        return "Squads"
    
    # DB Meta Getters
    def getColumnMetaName(self, table_name: str, short_name: str, config_mgr: ConfigManager, squad_type: str = "Squads") -> Optional[str]:
        """Get column name for a given shortname in a table from metadata based on selected game and squad type."""
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None
        
        meta = self.main_data_manager.getDbMeta(profile.id.lower(), squad_type)
        table_data = meta.get(table_name)
        if table_data:
            for field in table_data["fields"]:
                if field["shortname"] == short_name:
                    return field["name"]
        return None

    def getTableMetaColumnOrder(self, table_name: str, config_mgr: ConfigManager, squad_type: str = "Squads") -> Optional[List[str]]:
        """Get the order of columns for a given table from metadata based on selected game and squad type."""
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None
        
        meta = self.main_data_manager.getDbMeta(profile.id.lower(), squad_type)
        table_data = meta.get(table_name)
        return [field["name"] for field in table_data["fields"]] if table_data else None
    # endregion

    # region Utility
    def getRelativeDate(self, date_str: str, is_title_update: bool = False) -> str:
        """Convert date string to relative time."""
        try:
            dt = None
            # new ISO 8601 format
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                # fall back to the old format
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
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse date {date_str}: {e}")
            return "Invalid Date"
    
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
        profile = self._get_profile(path)
        
        if profile:
            exe_path = os.path.join(path, profile.exe_name)
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
        
    def getGameSemVer(self, config_mgr: ConfigManager) -> Optional[str]:
        """Get game SemVer from installerdata.xml."""
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None

        installerdata_path = os.path.join(config_mgr.getConfigKeySelectedGame(), profile.semver_relative_path)
        try:
            return ET.parse(installerdata_path).find(".//gameVersion").attrib["version"]
        except (FileNotFoundError, ET.ParseError, AttributeError, KeyError) as e:
            ErrorHandler.handleError(f"Failed to get SemVer: {e}")
            return None

    def getLiveEditorVersion(self, config_mgr: ConfigManager) -> Optional[str]:
        """Get Live Editor version from changelog.txt via registry."""
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None
        
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, profile.live_editor_registry_key) as key:
                dir_path = winreg.QueryValueEx(key, profile.live_editor_registry_value_name)[0]
            for file_name in os.listdir(dir_path):
                if "changelog" in file_name.lower():
                    file_path = os.path.join(dir_path, file_name)
                    with open(file_path, "r", encoding="utf-8") as f:
                        if match := re.match(r"v\d+\.\d+\.\d+", f.read()):
                            return match.group(0)
        except (WindowsError, FileNotFoundError, re.error) as e:
            ErrorHandler.handleError(f"Failed to get Live Editor version: {e}")
            return None
            
    def getPatchVersion(self, game_path: str) -> Optional[int]:
        """Get patch version from layout.toc"""
        profile = self._get_profile(game_path)
        if not profile: return None

        toc_path = os.path.join(game_path, profile.patch_version_relative_path)
        try:
            with open(toc_path, "rb") as f:
                data = f.read()
                pos = data.find(b"head\x00")
                if pos == -1 or pos + 9 > len(data):
                    return None
                return int.from_bytes(data[pos + 5:pos + 9], "little")
        except Exception as e:
            ErrorHandler.handleError(f"Failed to get Patch Version from {toc_path}: {e}")
            return None
    # endregion

    # region
    def getFETPath(self) -> Optional[str]:
        try:
            key_path = r"FIFAEditorTool.fifaproject\DefaultIcon"
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
                path_with_comma = winreg.QueryValueEx(key, None)[0]
                exe_path = path_with_comma.split(',')[0].strip('"')
                if os.path.exists(exe_path):
                    return os.path.dirname(exe_path)
        except Exception as e:
            ErrorHandler.handleError(f"Error accessing registry for FIFA Editor Tool: {e}")
        return None

    def getFETChangeFolders(self, config_mgr: ConfigManager) -> Optional[Dict]:
        try:
            profile = self._get_profile_from_config(config_mgr)
            if not profile:
                ErrorHandler.handleError("Could not determine game profile from config.")
                return None

            fet_path = self.getFETPath()
            if not fet_path:
                ErrorHandler.handleError("FIFA Editor Tool path not found in registry.")
                return None

            data_folder_path = os.path.join(fet_path, "FIFA Editor Tool Data", profile.fet_data_profile_name)
            if not os.path.isdir(data_folder_path):
                ErrorHandler.handleError(f"FET data folder not found for the selected game: {data_folder_path}")
                return {"path": data_folder_path, "folders": []}

            game_content = self.loadGameContent(config_mgr.getConfigKeySelectedGame(), config_mgr=config_mgr)
            title_updates = game_content.get(self.getProfileTypeTitleUpdate(), {}).get(self.getContentKeyTitleUpdate(), [])
            
            patch_id_to_tu_map = {}
            for tu in title_updates:
                patch_id = tu.get(self.getTitleUpdatePatchIDKey())
                tu_name_full = tu.get(self.getTitleUpdateNameKey())

                if not patch_id or not tu_name_full:
                    continue

                short_name = ""
                if "title update" in tu_name_full.lower():
                    match = re.search(r'title update\s+([\d\.]+)', tu_name_full, re.IGNORECASE)
                    if match:
                        short_name = f"TU {match.group(1).strip()}"
                else:
                    match = re.search(r'(\d+(\.\d+)+)', tu_name_full)
                    if match:
                        short_name = f"v{match.group(1).strip()}"
                
                if not short_name:
                    short_name = tu_name_full.split(' - ')[-1].strip()

                patch_id_to_tu_map[patch_id] = short_name

            folders_to_rename = []
            folder_name_pattern = re.compile(r"From (\d+) to (\d+)(?: \((.+)\))?")

            for folder_name in os.listdir(data_folder_path):
                original_path = os.path.join(data_folder_path, folder_name)
                if os.path.isdir(original_path):
                    match = folder_name_pattern.match(folder_name)
                    if match:
                        id1, id2, date = match.groups()
                        
                        start_name = patch_id_to_tu_map.get(id1)
                        end_name = patch_id_to_tu_map.get(id2)

                        if start_name and end_name:
                            suffix = f" ({date})" if date else folder_name.split(f"{id2}")[-1]
                            new_name = f"From {start_name} to {end_name}{suffix}"
                            if new_name != folder_name:
                                folders_to_rename.append({
                                    "original_path": original_path,
                                    "original_name": folder_name,
                                    "new_name": new_name
                                })
            
            return {"path": data_folder_path, "folders": sorted(folders_to_rename, key=lambda x: x['original_name'])}

        except Exception as e:
            ErrorHandler.handleError(f"An error occurred while getting FET change folders: {e}")
            return None

    def getFIFAModManagerPath(self) -> Optional[str]:
        try:
            key_path = r"FIFAModManager.fifamod\DefaultIcon"
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
                path_with_comma = winreg.QueryValueEx(key, None)[0]
                exe_path = path_with_comma.split(',')[0].strip('"')
                if os.path.exists(exe_path):
                    return os.path.dirname(exe_path)
        except Exception as e:
            ErrorHandler.handleError(f"Error accessing registry for FIFA Mod Manager: {e}")
        return None

    def loadModManagerConfig(self) -> Optional[Dict]:
        manager_path = self.getFIFAModManagerPath()
        if not manager_path:
            return None
        
        config_path = os.path.join(manager_path, "FIFA Mod Manager.json")
        if not os.path.exists(config_path):
            logger.error(f"FIFA Mod Manager config not found at: {config_path}")
            return None
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            ErrorHandler.handleError(f"Failed to read or parse FIFA Mod Manager config: {e}")
            return None

    def getModsCompatibilitInfo(self, config_mgr: ConfigManager, profile_name: Optional[str] = None, custom_file_paths: Optional[List[str]] = None) -> Optional[Dict]:
        game_path = config_mgr.getConfigKeySelectedGame()
        if not game_path:
            ErrorHandler.handleError("No game selected in the tool's config.")
            return None

        profile = self._get_profile(game_path)
        if not profile:
            ErrorHandler.handleError(f"Could not determine game profile from path: {game_path}")
            return None
        
        game_id = profile.id
        current_patch_version = self.getPatchVersion(game_path)
        game_content = self.loadGameContent(game_path)
        title_updates = game_content.get(self.getProfileTypeTitleUpdate(), {}).get(self.getContentKeyTitleUpdate(), [])

        current_tu_name = "Unknown"
        if current_patch_version:
            for tu in title_updates:
                if tu.get(self.getTitleUpdatePatchIDKey()) == str(current_patch_version):
                    current_tu_name = tu.get(self.getTitleUpdateNameKey(), f"TU with PatchID {current_patch_version}").split(" - ", 1)[-1]
                    break

        mods_info = []

        if custom_file_paths:
            for mod_file_path in custom_file_paths:
                try:
                    mod_reader_instance = ModReaderFactory.get_reader(mod_file_path)
                    mod_data = mod_reader_instance.read()
                    
                    if not mod_data or mod_data.game_profile.lower() != game_id.lower():
                        continue
                    
                    mod_patch_version = mod_data.game_version
                    mod_tu_name = "Unknown"
                    for tu in title_updates:
                        if tu.get(self.getTitleUpdatePatchIDKey()) == str(mod_patch_version):
                            mod_tu_name = tu.get(self.getTitleUpdateNameKey(), f"TU with PatchID {mod_patch_version}").split(" - ", 1)[-1]
                            break

                    compatibility_status = "INCOMPATIBLE"
                    if current_patch_version is not None:
                        if current_patch_version == mod_patch_version:
                            compatibility_status = "COMPATIBLE"
                        else:
                            has_legacy_files = any(r.resource_type.name == "LEGACY" for r in mod_data.resources)
                            compatibility_status = "INCOMPATIBLE" if has_legacy_files else "UNCERTAIN"
                    
                    resources = [{"name": r.name, "type": r.resource_type.name, "legacy_chunk_name": r.legacy_chunk_name} for r in mod_data.resources]

                    mods_info.append({
                        "title": mod_data.mod_title, "author": mod_data.mod_author, "description": mod_data.description,
                        "target_tu": mod_tu_name, "compatibility_status": compatibility_status,
                        "is_enabled": False, "icon_data": mod_data.icon,
                        "resources": resources, "file_path": mod_file_path,
                    })
                except Exception as e:
                    logger.error(f"Failed to read custom mod file {os.path.basename(mod_file_path)}: {e}")
            
            return {"current_game_tu": current_tu_name, "mods": mods_info}

        else:
            mod_manager_path = self.getFIFAModManagerPath()
            if not mod_manager_path:
                ErrorHandler.handleError("Could not find FIFA Mod Manager path.")
                return None
            
            mods_folder = os.path.join(mod_manager_path, "Mods", profile.mod_manager_profile_name)
            
            if game_id not in self._mods_cache:
                all_mods_data = []
                if os.path.exists(mods_folder):
                    all_mod_files = [f for f in os.listdir(mods_folder) if f.endswith('.fifamod')]
                    for mod_filename in all_mod_files:
                        mod_file_path = os.path.join(mods_folder, mod_filename)
                        try:
                            mod_reader_instance = ModReaderFactory.get_reader(mod_file_path)
                            mod_data = mod_reader_instance.read()
                            if not mod_data or mod_data.game_profile.lower() != game_id.lower():
                                continue
                            all_mods_data.append({"filename": mod_filename, "file_path": mod_file_path, "data": mod_data})
                        except Exception as e:
                            logger.error(f"Failed to read mod file {mod_filename}: {e}")
                self._mods_cache[game_id] = all_mods_data
            
            cached_mods = self._mods_cache[game_id]
            
            mod_manager_config = self.loadModManagerConfig()
            if not mod_manager_config:
                ErrorHandler.handleError("Could not find or load FIFA Mod Manager configuration.")
                return None

            profiles_data = mod_manager_config.get("Profiles", {}).get(game_id, [])
            profile_names = [p.get("Name") for p in profiles_data] if profiles_data else ["Default Profile"]
            
            target_profile_name = profile_name or mod_manager_config.get("LastUsedProfileName", {}).get(game_id, "Default Profile")
            applied_mods_config = []
            for p in profiles_data:
                if p.get("Name") == target_profile_name:
                    applied_mods_config = p.get("AppliedMods", [])
                    break
            
            applied_mod_files = {mod['ModFilePath'] for mod in applied_mods_config}

            for mod_item in cached_mods:
                mod_data = mod_item["data"]
                mod_filename = mod_item["filename"]
                mod_file_path = mod_item.get("file_path", os.path.join(mods_folder, mod_filename))
                mod_patch_version = mod_data.game_version
                mod_tu_name = "Unknown"
                for tu in title_updates:
                    if tu.get(self.getTitleUpdatePatchIDKey()) == str(mod_patch_version):
                        mod_tu_name = tu.get(self.getTitleUpdateNameKey(), f"TU with PatchID {mod_patch_version}").split(" - ", 1)[-1]
                        break

                compatibility_status = "INCOMPATIBLE"
                if current_patch_version is not None:
                    if current_patch_version == mod_patch_version:
                        compatibility_status = "COMPATIBLE"
                    else:
                        has_legacy_files = any(r.resource_type.name == "LEGACY" for r in mod_data.resources)
                        compatibility_status = "INCOMPATIBLE" if has_legacy_files else "UNCERTAIN"
                
                is_enabled = mod_filename in applied_mod_files
                resources = [{"name": r.name, "type": r.resource_type.name, "legacy_chunk_name": r.legacy_chunk_name} for r in mod_data.resources]

                mods_info.append({
                    "title": mod_data.mod_title, "author": mod_data.mod_author, "description": mod_data.description,
                    "target_tu": mod_tu_name, "compatibility_status": compatibility_status,
                    "is_enabled": is_enabled, "icon_data": mod_data.icon,
                    "resources": resources, "file_path": mod_file_path,
                })

            return {
                "profiles": profile_names, "current_profile": target_profile_name,
                "current_game_tu": current_tu_name, "mods": mods_info
            }
    
    def getInstalledCurrentTitleUpdate(self, config_mgr: ConfigManager) -> Optional[Dict[str, Any]]:
        if not (profile := self._get_profile_from_config(config_mgr)): return None
        content = self.loadGameContent(config_mgr.getConfigKeySelectedGame(), config_mgr=config_mgr)
        return next((u for u in content.get(self.getProfileTypeTitleUpdate(), {}).get(self.getContentKeyTitleUpdate(), []) if u.get(self.getTitleUpdateSHA1Key()) == config_mgr.getConfigKeySHA1()), None)
        
    def getSelectedUpdate(self, tab_key: str, table_component) -> Optional[str]:
        if not (table_component and hasattr(table_component, 'table')):
            return None

        row = -1
        if selected := table_component.table.selectedIndexes():
            row = selected[0].row()
        else:
            row = table_component.table.currentRow()

        if row >= 0:
            name_key = self.getTitleUpdateNameKey() if tab_key == self.getTabKeyTitleUpdates() else self.getSquadsNameKey() if tab_key == self.getTabKeySquadsUpdates() else self.getFutSquadsNameKey()
            item = table_component.table.item(row, 0)
            if item:
                return item.text()
        return None
    
    def fetchPatchNotesData(self, patch_notes_url: str) -> Optional[Dict[str, Any]]:
        if not patch_notes_url:
            return None
        try:
            response = requests.get(patch_notes_url, timeout=self.TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            cover_url = None
            if cover := data.get("cover"):
                if scaled_images := cover.get("scaled"):
                    cover_url = scaled_images[-1].get("url")

            creation_date = None
            if actions := data.get("actions"):
                create_action = next((action for action in actions if action.get("type") == "createCard"), None)
                if create_action:
                    creation_date = create_action.get("date")

            return {
                "title": data.get("name", "Patch Notes"),
                "description": data.get("desc", "No description available."),
                "shortUrl": data.get("shortUrl"),
                "coverUrl": cover_url,
                "lastActivity": data.get("dateLastActivity"),
                "creationDate": creation_date
            }
        except requests.RequestException as e:
            ErrorHandler.handleError(f"Failed to fetch patch notes from {patch_notes_url}: {e}")
            return None
        except Exception as e:
            ErrorHandler.handleError(f"Failed to parse patch notes JSON from {patch_notes_url}: {e}")
            return None
            
    def fetchLiveEditorVersionsData(self, config_mgr: ConfigManager) -> Optional[Dict]:
        profile = self._get_profile_from_config(config_mgr)
        if not profile: return None

        url = f"https://raw.githubusercontent.com/xAranaktu/FC-{profile.version}-Live-Editor/main/version.json"
        
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

    def fetchDepotManifest(self, game_id: str, depot_type: str, depot_id: str, manifest_id: str) -> Optional[Manifest]:
        """Fetches and parses a depot manifest file from GitHub directly into memory."""
        url = f"https://raw.githubusercontent.com/{GITHUB_ACC}/{UPDATES_REPO}/main/Profiles/{game_id}/Depot/Manifests/{depot_type}/manifest_{depot_id}_{manifest_id}.txt"

        if url in self._depot_manifest_cache:
            return self._depot_manifest_cache[url]

        try:
            response = requests.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            manifest_content = response.text

            manifest_data = Manifest.from_string(manifest_content)

            self._depot_manifest_cache[url] = manifest_data
            return manifest_data

        except requests.RequestException as e:
            logger.error(f"Failed to fetch depot manifest from {url}: {e}")
            return None
        except ValueError as e:
            ErrorHandler.handleError(f"Failed to parse manifest file from {url}: {e}")
            return None
        except Exception as e:
            ErrorHandler.handleError(f"An unexpected error occurred while processing manifest {url}: {e}")
            return None
        
    def fetchDepotChangelog(self, game_id: str, depot_type: str, manifest_id: str) -> Optional[Dict]:
        url = f"https://raw.githubusercontent.com/{GITHUB_ACC}/{UPDATES_REPO}/main/Profiles/{game_id}/Depot/Changelogs/{depot_type}/{manifest_id}.json"

        if url in self._depot_changelog_cache:
            return self._depot_changelog_cache[url]

        try:
            response = requests.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            data = response.json()
            self._depot_changelog_cache[url] = data
            return data
        except requests.RequestException as e:
            logger.error(f"Failed to fetch depot changelog from {url}: {e}")
            return None

    def getDepotTypeMain(self) -> str:
        return "Main"

    def getDepotTypeLanguage(self) -> str:
        return "Language"
    # endregion