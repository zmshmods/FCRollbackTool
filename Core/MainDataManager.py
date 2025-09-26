import os, sys
from typing import Optional, Dict, List
import xml.etree.ElementTree as ET

try:
    from Core.key import key  # type: ignore
except ModuleNotFoundError:
    key = None
    logger.warning("Core.key module not available in the source code.")
from Core.Logger import logger
from Core.ErrorHandler import ErrorHandler

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
        if getattr(sys, 'frozen', False):
            self.application_path = os.path.dirname(sys.executable)
        else:
            self.application_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        self.basePath = os.path.join(self.application_path, "Data")
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

        dbmeta_file = f"fifa_ng_db-meta.xml" if squad_type == "Squads" else "cards_ng_db-meta.xml"
        dbmeta_path = self.getPath(os.path.join("DB", game_version.upper(), dbmeta_file))
        if not dbmeta_path:
            ErrorHandler.handleError(f"Metadata file not found: {dbmeta_file} for {game_version}")
            return {}

        try:
            tree = ET.parse(dbmeta_path)
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
            ErrorHandler.handleError(f"Error parsing metadata file {dbmeta_file} for {game_version}: {e}")
            return {}