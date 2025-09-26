import os
import time
import subprocess
import cloudscraper
import certifi
import re
import logging
import shutil
from datetime import datetime
from lxml import html
import base64
from PySide6.QtCore import QThread, Signal
from Core.Logger import logger
from Core.MainDataManager import MainDataManager
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.AppDataManager import AppDataManager
from Core.NotificationManager import NotificationHandler
from Core.ErrorHandler import ErrorHandler

LOG_DIR, DOWNLOAD_LOG_DIR = "Logs", os.path.join("Logs", "DownloadLogs")

class DownloadCore(QThread):
    progress_signal = Signal(float, float, float, float, str, int, int)
    paused_signal = Signal()
    resumed_signal = Signal()
    cancel_status_signal = Signal(str)
    download_completed_signal = Signal()
    download_started_signal = Signal()
    error_signal = Signal()

    def __init__(self, url: str, game_profile: str, update_name: str, tab_key: str):
        super().__init__()
        self.url = url
        self.game_profile = game_profile
        self.update_name = update_name
        self.tab_key = tab_key
        self.cancel_flag = False
        self.is_paused = False
        self.error_occurred = False
        self.stop_flag = False
        self.process = None
        self.cleaned = False  # Flag to track if temp folder has been cleaned
        self.config_manager = ConfigManager()
        self.game_manager = GameManager()
        self.use_idm = self.config_manager.getConfigKeyAutoUseIDM() and os.path.exists(self.config_manager.getConfigKeyIDMPath() or "")
        self.download_logger = self._setup_logger()
        if not self.use_idm:
            temp_folder = AppDataManager.getTempFolder()
            subfolder = os.path.join(temp_folder, self.update_name)
            os.makedirs(subfolder, exist_ok=True)

    def _setup_logger(self) -> logging.Logger:
        if self.use_idm or not self.config_manager.getConfigKeyEnableDownloadLogs():
            logger = logging.getLogger(f"NullDownload_{self.update_name}")
            logger.addHandler(logging.NullHandler())
            return logger
        os.makedirs(DOWNLOAD_LOG_DIR, exist_ok=True)
        log_file = os.path.join(DOWNLOAD_LOG_DIR, f"{self.update_name} {datetime.now():%Y-%m-%d %H.%M.%S}.log")
        handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        dl_logger = logging.getLogger(f"Download_{self.update_name}")
        dl_logger.setLevel(logging.DEBUG)
        dl_logger.addHandler(handler)
        dl_logger.propagate = False
        return dl_logger

    def _get_direct_url(self) -> str:
        if "mediafire" not in self.url.lower():
            return self.url
        try:
            scraper = cloudscraper.create_scraper()
            for _ in range(2):
                response = scraper.get(self.url, headers={"User-Agent": "Mozilla/5.0"}, verify=certifi.where())
                if response.status_code == 200:
                    tree = html.fromstring(response.text)
                    
                    scrambled_link = tree.xpath('//a[@id="downloadButton"]/@data-scrambled-url')
                    if scrambled_link and scrambled_link[0]:
                        decoded_url = base64.b64decode(scrambled_link[0]).decode('utf-8')
                        if decoded_url and not decoded_url.startswith('#') and not decoded_url.endswith('#'):
                            return decoded_url
                    
                    direct_link = tree.xpath('//a[@id="downloadButton"]/@href')
                    if direct_link and direct_link[0]:
                        url = direct_link[0]
                        if url.startswith("https://"):
                            return url

                time.sleep(1)
            raise ValueError("Failed to retrieve direct download URL from MediaFire.")
        except Exception as e:
            ErrorHandler.handleError(str(e))
            self.error_signal.emit()
            return ""

    def _get_download_config(self, source: str) -> tuple:
        try:
            if self.tab_key == self.game_manager.getTabKeyTitleUpdates():
                profile_subfolder = self.game_manager.getProfileTypeTitleUpdate()
            else:
                profile_subfolder = self.game_manager.getProfileTypeSquad()

            if not profile_subfolder:
                ErrorHandler.handleError("Invalid tab key for download configuration")
                self.error_signal.emit()
                return ([], "", "")

            profile_folder = self.game_manager.getProfileDirectory(self.game_profile, profile_subfolder)
            
            # Create specific sub-folders for Squads/FutSquads inside the main profile folder
            if self.tab_key == self.game_manager.getTabKeySquadsUpdates():
                profile_folder = os.path.join(profile_folder, self.game_manager.getContentKeySquad())
            elif self.tab_key == self.game_manager.getTabKeyFutSquadsUpdates():
                profile_folder = os.path.join(profile_folder, self.game_manager.getContentKeyFutSquad())

            os.makedirs(profile_folder, exist_ok=True)
            filename = f"{self.update_name}.rar" if self.tab_key == self.game_manager.getTabKeyTitleUpdates() else self.update_name
            final_path = os.path.join(profile_folder, filename)

            if source == "aria2":
                aria2c_path = MainDataManager().getAria2c() or ""
                if not aria2c_path:
                    ErrorHandler.handleError("Aria2c executable not found")
                    self.error_signal.emit()
                    return ([], "", "")
                segments = self.config_manager.getConfigKeySegments() or "8"
                speed_limit = []
                if self.config_manager.getConfigKeySpeedLimitEnabled():
                    limit = self.config_manager.getConfigKeySpeedLimit()
                    if isinstance(limit, (str, int)) and str(limit).isdigit():
                        speed_limit = ["--max-overall-download-limit", f"{limit}K"]
                return ([
                    aria2c_path, "--log-level=debug", "--dir", os.path.join(AppDataManager.getTempFolder(), self.update_name),
                    "--continue=true", "--split", segments, "--max-connection-per-server=8", *speed_limit, self.url
                ], os.path.join(AppDataManager.getTempFolder(), self.update_name), final_path)
            idm_path = self.config_manager.getConfigKeyIDMPath() or ""
            if not os.path.exists(idm_path):
                ErrorHandler.handleError("IDM executable not found")
                self.error_signal.emit()
                return ([], "", "")
            return ([idm_path, "/d", self.url, "/p", profile_folder, "/f", filename, "/n"], profile_folder, final_path)
        except Exception as e:
            ErrorHandler.handleError(f"Error configuring download: {str(e)}")
            self.error_signal.emit()
            return ([], "", "")

    def _check_disk_space(self) -> bool:
        try:
            disk_usage = shutil.disk_usage(os.getenv("SystemDrive", "C:"))
            if (free_space_gb := disk_usage.free / (1024 ** 3)) < 10:
                msg = f"Low disk space detected! Only {free_space_gb:.2f} GB free."
                NotificationHandler.showWarning(msg)
                logger.warning(msg)
            return True
        except Exception as e:
            ErrorHandler.handleError(f"Error checking disk space: {str(e)}")
            self.error_signal.emit()
            return False

    def _start_process(self, source: str, command: list) -> bool:
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1, startupinfo=startupinfo)
            for _ in range(10):
                if self.process.poll() is None:
                    break
                time.sleep(0.05)
            else:
                ErrorHandler.handleError(f"{source} process failed to start")
                self.error_signal.emit()
                return False
            self.download_started_signal.emit()
            return True
        except Exception as e:
            ErrorHandler.handleError(f"Failed to start {source} process: {str(e)}")
            self.error_signal.emit()
            return False

    def _move_file(self, temp_folder: str, final_path: str) -> str:
        try:
            for file_name in os.listdir(temp_folder):
                temp_path = os.path.join(temp_folder, file_name)
                target_path = final_path
                if os.path.exists(target_path):
                    base, ext = os.path.splitext(file_name)
                    counter = 1
                    while os.path.exists(target_path):
                        target_path = os.path.join(os.path.dirname(final_path), f"{base} ({counter}){ext}")
                        counter += 1
                shutil.move(temp_path, target_path)
                return target_path
            ErrorHandler.handleError("No files found to move from temp folder")
            self.error_signal.emit()
            return ""
        except Exception as e:
            ErrorHandler.handleError(f"Error moving file: {str(e)}")
            self.error_signal.emit()
            return ""

    def _process_download(self, source: str, command: list, check_path: str, final_path: str) -> bool:
        try:
            if self.config_manager.getConfigKeyEnableDownloadLogs():
                self.download_logger.debug(f"Executing {source.upper()} command: {' '.join(command)}")

            if not self._start_process(source, command):
                return False

            if source == "aria2":
                log_progress = self.config_manager.getConfigKeyLogDownloadProgress()
                while not self.cancel_flag and (line := self.process.stdout.readline()):
                    while self.is_paused and not self.cancel_flag:
                        time.sleep(0.1)
                    is_progress_line = line.strip().startswith('[') and '#' in line
                    if self.config_manager.getConfigKeyEnableDownloadLogs() and (not is_progress_line or log_progress) and line.strip():
                        self.download_logger.debug(f"aria2c stdout: {line.strip()}")
                    if is_progress_line:
                        patterns = [
                            r'(\d+\.?\d*[KMG]?i?B)/(\d+\.?\d*[KMG]?i?B)',
                            r'\((\d+)%\)',
                            r'DL:(\d+\.?\d*[KMG]?i?B)',
                            r'ETA:(\d+[hm]?\d*[ms]?)',
                            r'CN:(\d+)'
                        ]
                        matches = [re.search(p, line) for p in patterns]
                        downloaded_mb = total_mb = percentage = rate_mb = 0.0
                        eta, connections = "N/A", 0
                        splits = int(self.config_manager.getConfigKeySegments() or 8)
                        if matches[0] and matches[0].groups():
                            downloaded, total = matches[0].groups()
                            downloaded_mb = self._convert_to_mb(downloaded)
                            total_mb = self._convert_to_mb(total)
                        if matches[1]:
                            percentage = float(matches[1].group(1))
                        if matches[2]:
                            rate_mb = self._convert_to_mb(matches[2].group(1))
                        if matches[3]:
                            eta = matches[3].group(1)
                        if matches[4]:
                            connections = int(matches[4].group(1))
                        self.progress_signal.emit(downloaded_mb, total_mb, percentage, rate_mb, eta, connections, splits)

                if self.cancel_flag:
                    return False

                returncode = self.process.wait()
                stderr_output = self.process.stderr.read()
                if self.config_manager.getConfigKeyEnableDownloadLogs() and stderr_output.strip():
                    self.download_logger.debug(f"aria2c stderr: {stderr_output.strip()}")

                if returncode != 0:
                    self.error_occurred = True
                    try:
                        exitStatus = {
                            1: "Unknown error occurred during download.\n" + (
                                "Check Logs > DownloadLog for details." if self.config_manager.getConfigKeyEnableDownloadLogs() else ""
                            ),
                            2: "Download timed out.",
                            3: "Resource not found on server.",
                            4: "Too many file not found errors.",
                            5: "Download speed too slow.",
                            6: "Internet connection issue.",
                            7: "Download interrupted with unfinished tasks.",
                            8: "Server does not support resume.",
                            9: "Not enough disk space.",
                            10: "Piece length mismatch.",
                            11: "File already being downloaded.",
                            13: "File already exists.",
                            14: "File renaming failed.",
                            15: "Could not open existing file.",
                            16: "Could not create/truncate file.",
                            17: "File I/O error.",
                            18: "Could not create directory.",
                            19: "Name resolution failed.",
                            22: "Invalid HTTP response.",
                            23: "Too many redirects.",
                            24: "HTTP authorization failed."
                        }
                        error_message = exitStatus.get(returncode, f"Unknown error with exit code: {returncode}")
                        if error_message:
                            ErrorHandler.handleError(error_message)
                    except Exception as e:
                        ErrorHandler.handleError(f"Failed to process aria2c error: {str(e)}")
                    self.error_signal.emit()
                    subfolder_path = os.path.join(AppDataManager.getTempFolder(), self.update_name)
                    if not self.use_idm and not self.cleaned and os.path.exists(subfolder_path):
                        AppDataManager.manageTempFolder(clean=True, subfolder=self.update_name)
                        self.cleaned = True
                    return False

                final_path = self._move_file(check_path, final_path)
                if not final_path:
                    return False
                logger.info(f"Download completed. File moved to: {final_path}")
                self.download_completed_signal.emit()
                return True
            else:  # IDM
                logger.info(f"IDM download started for: {self.update_name}")
                
                initial_mod_time = -1
                if os.path.exists(final_path):
                    initial_mod_time = os.path.getmtime(final_path)
                    logger.debug(f"Existing file found. Initial mod time: {initial_mod_time}")

                while not self.stop_flag:
                    if os.path.exists(final_path):
                        if initial_mod_time == -1:
                            logger.info(f"New file detected in profile: {self.update_name}")
                            self.download_completed_signal.emit()
                            return True
                        
                        current_mod_time = os.path.getmtime(final_path)
                        if current_mod_time > initial_mod_time:
                            logger.info(f"File modification detected. Assuming download complete for: {self.update_name}")
                            self.download_completed_signal.emit()
                            return True
                    time.sleep(1)
                logger.info("IDM download waiting stopped.")
                return False
        except Exception as e:
            if self.config_manager.getConfigKeyEnableDownloadLogs():
                self.download_logger.error(f"Error processing download: {str(e)}")
            ErrorHandler.handleError(f"Error processing download: {str(e)}")
            self.error_signal.emit()
            subfolder_path = os.path.join(AppDataManager.getTempFolder(), self.update_name)
            if not self.use_idm and not self.cleaned and os.path.exists(subfolder_path):
                AppDataManager.manageTempFolder(clean=True, subfolder=self.update_name)
                self.cleaned = True
            return False

    def _convert_to_mb(self, value: str) -> float:
        try:
            if not (match := re.match(r'(\d+\.?\d*)([KMG]i?B)?', value)):
                return 0.0
            value, unit = float(match.group(1)), match.group(2) or ""
            return value * (1024 if unit == 'GiB' else 1 if unit == 'MiB' else 0.001 if unit == 'KiB' else 1)
        except Exception as e:
            ErrorHandler.handleError(f"Error converting to MB: {str(e)}")
            self.error_signal.emit()
            return 0.0

    def run(self):
        source = "idm" if self.use_idm else "aria2"
        logger.info(f"Starting download: {self.update_name} with {source.upper()}")
        
        if self.tab_key in [self.game_manager.getTabKeySquadsUpdates(), self.game_manager.getTabKeyFutSquadsUpdates()]:
            squad_url = self.game_manager.getSquadFilePathKey(self.url, self.config_manager)
            if not squad_url:
                ErrorHandler.handleError(f"Failed to fetch SquadFilePath from {self.url}")
                self.error_signal.emit()
                return
            self.url = squad_url
            logger.info(f"Using SquadFilePath URL: {self.url}")
        
        self.url = self._get_direct_url()
        if not self.url:
            return
        
        command, check_path, final_path = self._get_download_config(source)
        if not command:
            return
        if not self._check_disk_space():
            return
        self._process_download(source, command, check_path, final_path)

    def pause(self):
        if not self.use_idm:
            self.is_paused = True
            self.paused_signal.emit()

    def resume(self):
        if not self.use_idm:
            self.is_paused = False
            self.resumed_signal.emit()

    def cancel(self):
        if not self.use_idm:
            self.cancel_flag = True
            self.cancel_status_signal.emit("canceling")
            if self.process:
                try:
                    if self.process.poll() is None:
                        self.process.terminate()
                        self.process.wait(timeout=1)
                except Exception:
                    pass
            subfolder_path = os.path.join(AppDataManager.getTempFolder(), self.update_name)
            if not self.cleaned and os.path.exists(subfolder_path):
                AppDataManager.manageTempFolder(clean=True, subfolder=self.update_name)
                self.cleaned = True
            self.cancel_status_signal.emit("canceled")
            logger.info("Download canceled.")
        else:
            self.stop_flag = True