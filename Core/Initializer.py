# --------------------------------------- Standard Libraries ---------------------------------------
import os
import json
import winreg
import ctypes
import zlib
from typing import Optional, Dict, Any
# --------------------------------------- Third-Party Libraries ---------------------------------------
import requests
# --------------------------------------- Project-specific Imports ---------------------------------------
from Core.Logger import logger

# الثوابت 
CONFIG_FILE = "config.json"
GAME_REGISTRY_KEYS = {
    "FC25.exe": r"SOFTWARE\EA Sports\EA SPORTS FC 25",
    "FC24.exe": r"SOFTWARE\EA Sports\EA SPORTS FC 24",
}

class Initializer:
    _config_cache: Optional[Dict[str, Any]] = None  # كاش داخلي لتخزين الكونفيغ

    @staticmethod
    def create_temp_folder(clean: bool = False) -> Optional[str]:
        temp_folder_path = os.path.join(os.getenv('LOCALAPPDATA'), "FC_Rollback_Tool", "Temp")
        try:
            if clean and os.path.exists(temp_folder_path):
                for root, dirs, files in os.walk(temp_folder_path, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                logger.info(f"Temp folder cleaned: {temp_folder_path}")

            os.makedirs(temp_folder_path, exist_ok=True)
            return temp_folder_path
        except Exception as e:
            logger.error(f"Error handling Temp folder: {e}")
            return None


    @staticmethod
    def initialize_and_load_config(updates: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        Initializer.create_temp_folder()

        if Initializer._config_cache and not updates:
            return Initializer._config_cache

        if not os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as config_file:
                    json.dump({"selected_game": None, "crc": None}, config_file, indent=4)
                logger.info(f"Config file created: {CONFIG_FILE}.")
            except Exception as e:
                Initializer.handle_error(f"Error creating config file: {e}")

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
                Initializer._config_cache = json.load(config_file)
                logger.info("Config loaded successfully.")
        except Exception as e:
            Initializer.handle_error(f"Error loading config file: {e}")
            Initializer._config_cache = {"selected_game": None, "crc": None}

        if updates:
            Initializer._config_cache.update(updates)
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as config_file:
                    json.dump(Initializer._config_cache, config_file, indent=4)
            except Exception as e:
                Initializer.handle_error(f"Error saving config file: {e}")

        return Initializer._config_cache

    @staticmethod
    def reset_selected_game() -> None:
        try:
            config = Initializer.initialize_and_load_config()
            if config.get("selected_game") is None:
                return
            Initializer.initialize_and_load_config({"selected_game": None, "crc": None})
            logger.info("Selected game has been reset.")
        except Exception as e:
            Initializer.handle_error(f"Error resetting selected game: {e}")

    @staticmethod
    def get_games_from_registry() -> Dict[str, str]:
        valid_paths = {}
        for exe_name, registry_key in GAME_REGISTRY_KEYS.items():
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_key) as key:
                    install_dir, _ = winreg.QueryValueEx(key, "Install Dir")
                    game_path = os.path.join(install_dir, exe_name)
                    if os.path.exists(game_path):
                        valid_paths[exe_name] = game_path
                        logger.info(f"Game found: {exe_name}")
            except FileNotFoundError:
                logger.warning(f"Registry key not found for {exe_name}.")
            except Exception as e:
                Initializer.handle_error(f"Error loading game profiles: {e}")
        return valid_paths

    @staticmethod
    def calculate_crc(file_path: str) -> Optional[str]:
        try:
            buf_size = 65536
            crc32_hash = 0
            with open(file_path, "rb") as f:
                while chunk := f.read(buf_size):
                    crc32_hash = zlib.crc32(chunk, crc32_hash)
            return f"{crc32_hash & 0xFFFFFFFF:08x}"
        except Exception as e:
            Initializer.handle_error(f"Error calculating CRC: {e}")
            return None

    @staticmethod
    def validate_and_update_crc(selected_game_path: str, table_widget_component: Optional[Any] = None) -> bool:
        if not selected_game_path:
            logger.info("No game selected.")
            return False

        config = Initializer.initialize_and_load_config()
        existing_crc = config.get("crc")

        for exe_name in GAME_REGISTRY_KEYS:
            exe_path = os.path.join(selected_game_path, exe_name)
            if os.path.exists(exe_path):
                current_crc = Initializer.calculate_crc(exe_path)

                if not existing_crc:  # إذا لم يكن هناك CRC سابق
                    Initializer.initialize_and_load_config({"crc": current_crc})
                    logger.info(f"Initial CRC calculation for {exe_name}: {current_crc}")
                elif current_crc != existing_crc:  # إذا كان الـ CRC مختلفًا
                    logger.info(f"Game TU change detected for {exe_name}. Hash recalculated and updated to: \"{current_crc}\"")
                    Initializer.initialize_and_load_config({"crc": current_crc})

                if table_widget_component:
                    table_widget_component.table_updated_signal.emit()

                return True

        logger.warning("Executable not found in the game path.")
        return False

    @staticmethod
    def load_game_content(selected_game_path: str) -> Optional[Dict[str, Any]]:
        try:
            game_folder_name = os.path.basename(selected_game_path.strip("\\/")).replace("EA SPORTS ", "")
            short_game_name = game_folder_name.replace(" ", "")  # إزالة المسافات مثل FC25

            folder_to_url_map = {
                "FC25": "https://raw.githubusercontent.com/zmshmods/FCRollbackToolUpdates/main/TitleUpdateProfiles/fc25.json",
                "FC24": "https://raw.githubusercontent.com/zmshmods/FCRollbackToolUpdates/main/TitleUpdateProfiles/fc24.json",
            }

            profiles_directory = os.path.join(os.getcwd(), "Profiles", short_game_name, "TitleUpdates")
            os.makedirs(profiles_directory, exist_ok=True)

            config_url = folder_to_url_map.get(short_game_name)
            if config_url:
                response = requests.get(config_url, timeout=3)
                if response.status_code == 200:
                    logger.info(f"Game configuration loaded for {short_game_name}.")
                    return response.json()
                else:
                    logger.error(f"Failed to fetch game content. Status code: {response.status_code}")
            else:
                logger.warning(f"No URL mapping found for {short_game_name}.")
        except requests.RequestException as e:
            logger.error(f"Error fetching game content: {e}")
        except Exception as e:
            logger.error(f"Error during load_game_content: {e}")
        return None

    @staticmethod
    def handle_error(message: str) -> None:
        logger.error(message)
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)