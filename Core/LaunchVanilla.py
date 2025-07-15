import os
import subprocess
import time
import threading
import psutil
import winreg
import shutil
from PySide6.QtCore import QTimer

from Core.Logger import logger
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.AppDataManager import AppDataManager
from Core.NotificationManager import NotificationHandler
from Core.ErrorHandler import ErrorHandler

# Constants
CHEAT_SERVICE_NAME = "EAAntiCheat.GameServiceLauncher.exe"
STEAM_APP_IDS = {"FC24": 2195250, "FC25": 2669320}
STOP_EVENT = threading.Event()

class VanillaLauncher:
    """Class to handle launching the game in vanilla mode."""
    def __init__(self, config_manager: ConfigManager = None, game_manager: GameManager = None):
        self.config_mgr = config_manager or ConfigManager()
        self.game_mgr = game_manager or GameManager()
        self.app_data_mgr = AppDataManager()

    def is_game_running(self, game_exe: str) -> bool:
        """Check if the game process is running."""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and os.path.basename(game_exe).lower() in proc.info['name'].lower():
                    logger.debug(f"Game process {proc.info['name']} is running.")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def terminate_game_process(self, game_exe: str) -> None:
        """Terminate the game process if running."""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and os.path.basename(game_exe).lower() in proc.info['name'].lower():
                    proc.terminate()
                    logger.info(f"Terminated game process: {proc.info['name']}")
                    time.sleep(2)  # Wait for process to terminate
                    return
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def wait_for_ea_processes(self, game_exe_name: str, timeout: int = 60) -> bool:
        """Wait for EA AntiCheat and game process to stabilize."""
        logger.info(f"Waiting for {CHEAT_SERVICE_NAME} and {game_exe_name}...")
        start_time = time.time()

        # Wait for AntiCheat to start
        while time.time() - start_time < timeout:
            if any(CHEAT_SERVICE_NAME.lower() in proc.info['name'].lower() for proc in psutil.process_iter(['name'])):
                logger.info(f"{CHEAT_SERVICE_NAME} has started.")
                break
            time.sleep(1)
        else:
            ErrorHandler.handleError(f"{CHEAT_SERVICE_NAME} did not start within {timeout} seconds.")
            return False

        # Wait for AntiCheat to exit
        while any(CHEAT_SERVICE_NAME.lower() in proc.info['name'].lower() for proc in psutil.process_iter(['name'])):
            time.sleep(1)
        logger.info(f"{CHEAT_SERVICE_NAME} has exited.")

        # Check if game is running
        start_time = time.time()
        while time.time() - start_time < 5:
            if self.is_game_running(game_exe_name):
                logger.info(f"Game process {game_exe_name} is running.")
                return True
            time.sleep(1)
        ErrorHandler.handleError(f"Game process {game_exe_name} did not start.")
        return False

    def get_steam_path(self) -> str:
        """Retrieve Steam installation path from registry."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
                logger.debug(f"Steam path found: {steam_path}")
                return steam_path
        except Exception as e:
            ErrorHandler.handleError(f"Failed to access Steam registry: {e}")
            return ""

    def backup_settings(self, settings_path: str) -> str:
        """Backup game settings to a temporary location."""
        backup_path = os.path.join(self.app_data_mgr.getBackupsFolder(), f"settings_backup_{int(time.time())}")
        if os.path.exists(settings_path):
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path, ignore_errors=True)
            shutil.copytree(settings_path, backup_path)
            shutil.rmtree(settings_path, ignore_errors=True)
            logger.info(f"Backed up settings from {settings_path} to {backup_path}")
        return backup_path

    def restore_settings(self, settings_path: str, backup_path: str) -> None:
        """Restore game settings from backup."""
        if os.path.exists(backup_path):
            if os.path.exists(settings_path):
                shutil.rmtree(settings_path, ignore_errors=True)
            shutil.copytree(backup_path, settings_path)
            shutil.rmtree(backup_path, ignore_errors=True)
            logger.info(f"Restored settings from {backup_path} to {settings_path}")
        else:
            logger.warning(f"Backup path {backup_path} does not exist for restoration.")

    def launch_vanilla(self) -> None:
        """Launch the game in vanilla mode in a separate thread."""
        def task():
            try:
                selected_game_path = self.config_mgr.getConfigKeySelectedGame()
                if not selected_game_path:
                    raise Exception("No game selected.")

                short_name = self.game_mgr.getShortGameName(selected_game_path)
                profile = self.game_mgr.getProfileByShortName(short_name)
                if not profile:
                    raise Exception(f"No profile found for {short_name}.")

                game_exe = os.path.join(selected_game_path, profile["exe_name"])
                if not os.path.exists(game_exe):
                    raise Exception(f"Game executable not found: {game_exe}")

                # Check if game is already running
                if self.is_game_running(game_exe):
                    response = NotificationHandler.showConfirmation(
                        f"{os.path.basename(game_exe)} is already running.\nWould you like to re-launch in vanilla mode?"
                    )
                    if response == "No":
                        return
                    self.terminate_game_process(game_exe)

                # Backup settings
                settings_path = self.game_mgr.getGameSettingsFolderPath(selected_game_path)
                backup_path = self.backup_settings(settings_path)

                # Launch game
                if "steam" in selected_game_path.lower():
                    steam_path = self.get_steam_path()
                    if not steam_path:
                        raise Exception("Steam path not found.")
                    app_id = STEAM_APP_IDS.get(short_name)
                    if not app_id:
                        raise Exception(f"Steam App ID not found for {short_name}.")
                    command = [os.path.join(steam_path, "Steam.exe"), "-applaunch", str(app_id)]
                    subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    logger.info(f"Launched via Steam with App ID: {app_id}")
                else:
                    subprocess.Popen([game_exe], creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB)
                    logger.info(f"Launched game: {game_exe}")

                # Wait for game to stabilize
                if not self.wait_for_ea_processes(os.path.basename(game_exe)):
                    raise Exception("Game failed to stabilize.")

                # Schedule settings restoration
                QTimer.singleShot(5000, lambda: self.restore_settings(settings_path, backup_path))

            except Exception as e:
                ErrorHandler.handleError(f"Failed to launch game in vanilla mode: {e}")
            finally:
                STOP_EVENT.set()

        threading.Thread(target=task, daemon=True).start()

def launch_vanilla_threaded(config_manager: ConfigManager = None, game_manager: GameManager = None):
    """Entry point to launch the game in vanilla mode."""
    launcher = VanillaLauncher(config_manager, game_manager)
    launcher.launch_vanilla()