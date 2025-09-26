import os
import subprocess
import time
import threading
import psutil
import winreg

from Core.Logger import logger
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.NotificationManager import NotificationHandler
from Core.ErrorHandler import ErrorHandler

STOP_EVENT = threading.Event()

class GameLauncher:
    def __init__(self, config_manager: ConfigManager = None, game_manager: GameManager = None):
        self.config_mgr = config_manager or ConfigManager()
        self.game_mgr = game_manager or GameManager()

    def is_game_running(self, game_exe: str) -> bool:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and os.path.basename(game_exe).lower() in proc.info['name'].lower():
                    logger.debug(f"Game process {proc.info['name']} is running.")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def terminate_game_process(self, game_exe: str) -> None:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and os.path.basename(game_exe).lower() in proc.info['name'].lower():
                    proc.terminate()
                    logger.info(f"Terminated game process: {proc.info['name']}")
                    time.sleep(2)
                    return
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def get_steam_path(self) -> str:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
                logger.debug(f"Steam path found: {steam_path}")
                return steam_path
        except Exception as e:
            ErrorHandler.handleError(f"Failed to access Steam registry: {e}")
            return ""

    def launch_game(self) -> None:
        def task():
            try:
                selected_game_path = self.config_mgr.getConfigKeySelectedGame()
                if not selected_game_path:
                    raise Exception("No game selected.")

                game_id = self.game_mgr.getSelectedGameId(selected_game_path)
                profile = self.game_mgr.profile_manager.get_profile(game_id)
                if not profile:
                    raise Exception(f"No profile found for {game_id}.")

                game_exe = os.path.join(selected_game_path, profile.exe_name)
                if not os.path.exists(game_exe):
                    raise Exception(f"Game executable not found: {game_exe}")

                if self.is_game_running(game_exe):
                    response = NotificationHandler.showConfirmation(
                        f"{profile.display_name} is already running.\nWould you like to terminate and re-launch it?"
                    )
                    if response != "Yes":
                        return
                    self.terminate_game_process(game_exe)

                if "steam" in selected_game_path.lower():
                    steam_path = self.get_steam_path()
                    if not steam_path:
                        raise Exception("Steam path not found.")
                    
                    app_id = profile.steam_app_id
                    if not app_id:
                        raise Exception(f"Steam App ID not found for {profile.display_name}.")
                        
                    command = [os.path.join(steam_path, "Steam.exe"), "-applaunch", str(app_id)]
                    subprocess.Popen(command)
                    logger.info(f"Launched {profile.display_name} via Steam with App ID: {app_id}")
                else:
                    subprocess.Popen([game_exe])
                    logger.info(f"Launched {profile.display_name}: {game_exe}")

            except Exception as e:
                ErrorHandler.handleError(f"Failed to launch game: {e}")
            finally:
                STOP_EVENT.set()

        threading.Thread(target=task, daemon=True).start()

def launch_game_threaded(config_manager: ConfigManager = None, game_manager: GameManager = None):
    launcher = GameLauncher(config_manager, game_manager)
    launcher.launch_game()