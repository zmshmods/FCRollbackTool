import os
import shutil
import zipfile
import py7zr
import rarfile
import pickle
import zlib
from enum import Enum

from PySide6.QtCore import QThread, Signal

from Core.Logger import logger
from Core.MainDataManager import MainDataManager
from Core.GameManager import GameManager
from Core.AppDataManager import AppDataManager
from Core.ErrorHandler import ErrorHandler

class ImportState(Enum):
    SEARCHING_EXECUTABLE = "Searching for executable file..."
    DETECTING_TITLE = "Detecting title update..."
    IMPORTING = "Importing to profile directory..."
    COMPLETED = "Completed successfully!"

class ImportTitleUpdate(QThread):
    state_changed = Signal(ImportState, int, str, bool)
    completed_signal = Signal()
    error_signal = Signal(str)
    cancel_signal = Signal()

    def __init__(self, input_path: str, game_mgr: GameManager, data_mgr: MainDataManager, app_data_mgr: AppDataManager, operation_id: str):
        super().__init__()
        self.input_path = input_path
        self.game_mgr = game_mgr
        self.data_mgr = data_mgr
        self.app_data_mgr = app_data_mgr
        self.operation_id = operation_id
        self.temp_path = os.path.join(self.app_data_mgr.getTempFolder(), f"ImportTitleUpdate_{operation_id}")
        self.exe_path_in_source = None
        self.is_canceled = False
        self.is_cleaned = False
        os.makedirs(self.temp_path, exist_ok=True)

    def get_file_size(self):
        try:
            size = os.path.getsize(self.input_path) if os.path.isfile(self.input_path) else \
                   sum(os.path.getsize(os.path.join(root, f)) for root, _, files in os.walk(self.input_path) for f in files)
            return f"{size / (1024 ** 3):.2f} GB" if size >= 1024 ** 3 else f"{size / (1024 ** 2):.2f} MB"
        except Exception as e:
            logger.error(f"Failed to calculate size for {self.input_path}: {str(e)}")
            return "Unknown size"

    def emit_state(self, state: ImportState, progress: int, details: str = "", is_success: bool = False):
        if not self.is_canceled:
            try:
                self.state_changed.emit(state, progress, details, is_success)
            except Exception as e:
                ErrorHandler.handleError(f"Failed to emit state: {str(e)}")
                if not self.is_canceled:
                    self.error_signal.emit(str(e))

    def cancel(self):
        if not self.is_canceled:
            self.is_canceled = True
            self._cleanup()
            self.cancel_signal.emit()
            self.quit()
            self.wait()

    def _handle_error(self, msg: str):
        ErrorHandler.handleError(msg)
        self.error_signal.emit(msg)
        self._cleanup()

    def run(self):
        zf = rf = szf = None
        try:
            ext = os.path.splitext(self.input_path)[1].lower()
            is_compressed = os.path.isfile(self.input_path) and ext in self.data_mgr.getCompressedFileExtensions()
            is_folder = os.path.isdir(self.input_path)
            
            expected_exes = [p.exe_name for p in self.game_mgr.profile_manager.get_all_profiles()]

            if not (is_compressed or is_folder):
                self._handle_error(f"Failed to import title update: No expected executable found in {self.input_path}.\nExpected: {', '.join(expected_exes)}")
                return

            exe_name = temp_exe_path = root_dir = None
            self.emit_state(ImportState.SEARCHING_EXECUTABLE, 10, "Searching for executable...")

            if is_compressed:
                try:
                    pwd = self.data_mgr.getKey()
                    if ext == ".zip":
                        zf = zipfile.ZipFile(self.input_path, "r")
                        if pwd: zf.setpassword(pwd.encode('utf-8'))
                    elif ext == ".7z":
                        szf = py7zr.SevenZipFile(self.input_path, "r", password=pwd)
                    elif ext == ".rar":
                        unrar_path = self.data_mgr.getUnRAR()
                        if not os.path.exists(unrar_path):
                            self._handle_error(f"UnRAR tool not found at: {unrar_path}")
                            return
                        rarfile.UNRAR_TOOL = unrar_path
                        rf = rarfile.RarFile(self.input_path, "r")
                        if pwd: rf.setpassword(pwd)
                    else:
                        self._handle_error(f"Unsupported archive type: {ext}")
                        return
                except Exception as e:
                    self._handle_error(f"Failed to open archive {self.input_path}: {str(e)}")
                    return

                archive_files = zf.namelist() if ext == ".zip" else szf.getnames() if ext == ".7z" else rf.namelist()
                for file in archive_files:
                    if os.path.basename(file).lower() in [e.lower() for e in expected_exes]:
                        self.exe_path_in_source = file
                        exe_name = os.path.basename(file)
                        root_dir = os.path.dirname(file)
                        break
                if not self.exe_path_in_source:
                    found_exes = sorted(list(set(os.path.basename(f) for f in archive_files if f.lower().endswith('.exe'))), key=lambda x: (not x.lower().startswith('f'), x))
                    found_exes = found_exes[:3]
                    self._handle_error(
                        f"Failed to import title update: No expected executable found in {self.input_path}.\n"
                        f"Expected: {' or '.join(expected_exes)}\nBut got:\n" + (''.join(f"- {exe}\n" for exe in found_exes) if found_exes else "no executable found\n")
                    )
                    return

                try:
                    if ext == ".zip":
                        zf.extract(self.exe_path_in_source, path=self.temp_path)
                    elif ext == ".7z":
                        szf.extract(targets=[self.exe_path_in_source], path=self.temp_path)
                    elif ext == ".rar":
                        rf.extract(self.exe_path_in_source, path=self.temp_path)
                    extracted_path = os.path.join(self.temp_path, self.exe_path_in_source)
                    temp_exe_path = os.path.join(self.temp_path, exe_name)
                    if os.path.exists(extracted_path):
                        os.makedirs(os.path.dirname(temp_exe_path), exist_ok=True)
                        shutil.move(extracted_path, temp_exe_path)
                    if not os.path.exists(temp_exe_path):
                        self._handle_error(f"Failed to extract executable: {exe_name} not found")
                        return
                    self.emit_state(ImportState.SEARCHING_EXECUTABLE, 50, f"{exe_name} found!", True)
                except Exception as e:
                    self._handle_error(f"Failed to extract executable {exe_name}: {str(e)}")
                    return
            else:
                for root, _, files in os.walk(self.input_path):
                    for file in files:
                        if file.lower() in [e.lower() for e in expected_exes]:
                            temp_exe_path = os.path.join(root, file)
                            self.exe_path_in_source = temp_exe_path
                            exe_name = os.path.basename(temp_exe_path)
                            root_dir = root
                            break
                    if temp_exe_path: break
                if not temp_exe_path:
                    found_exes = sorted(list(set(os.path.basename(f) for root, _, files in os.walk(self.input_path) for f in files if f.lower().endswith('.exe'))), key=lambda x: (not x.lower().startswith('f'), x))
                    found_exes = found_exes[:3]
                    self._handle_error(
                        f"Failed to import title update: No expected executable found in {self.input_path}.\n"
                        f"Expected: {' or '.join(expected_exes)}\nBut got:\n" + (''.join(f"- {exe}\n" for exe in found_exes) if found_exes else "no executable found\n")
                    )
                    return
                dst = os.path.join(self.temp_path, exe_name)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(temp_exe_path, dst)
                temp_exe_path = dst
                self.emit_state(ImportState.SEARCHING_EXECUTABLE, 50, f"{exe_name} found!", True)

            self.emit_state(ImportState.DETECTING_TITLE, 60, "Validating SHA1...")
            sha1 = self.game_mgr.calculateSHA1(temp_exe_path)
            if not sha1:
                self._handle_error(f"Failed to calculate SHA1 for executable")
                return

            profile = self.game_mgr.profile_manager.get_profile_by_exe(exe_name)
            if not profile:
                 self._handle_error(f"Could not find a game profile for executable: {exe_name}")
                 return
            
            short_game_name = profile.id
            cache_file = os.path.join(self.app_data_mgr.getDataFolder(), f"{short_game_name}.cache")
            if not os.path.exists(cache_file):
                cache_file = os.path.join(self.data_mgr.getBaseCache(), f"{short_game_name}.cache")

            try:
                with open(cache_file, "rb") as file:
                    content = pickle.loads(zlib.decompress(file.read()))
            except Exception as e:
                self._handle_error(f"Failed to load cache for {short_game_name}: {str(e)}")
                return

            title_updates = content.get(self.game_mgr.getProfileTypeTitleUpdate(), {}).get(self.game_mgr.getContentKeyTitleUpdate(), [])
            update = next((u for u in title_updates if u.get(self.game_mgr.getTitleUpdateSHA1Key()) == sha1), None)
            if not update:
                self._handle_error(f"No matching Title Update found for SHA1: {sha1}")
                return
            update_name = update.get(self.game_mgr.getTitleUpdateNameKey())
            self.emit_state(ImportState.DETECTING_TITLE, 80, f"Found {update_name} ({sha1})", True)

            target_dir = self.game_mgr.getProfileDirectory(short_game_name, self.game_mgr.getProfileTypeTitleUpdate())
            os.makedirs(target_dir, exist_ok=True)
            update_size = self.get_file_size()
            final_path = os.path.join(target_dir, f"{update_name}{ext}" if is_compressed else update_name)
            self.emit_state(ImportState.IMPORTING, 90, f"Importing {update_name} ({update_size})")

            if is_compressed:
                if os.path.exists(final_path):
                    os.remove(final_path)
                shutil.copy2(self.input_path, final_path)
            else:
                if os.path.exists(final_path):
                    shutil.rmtree(final_path, ignore_errors=True)
                os.makedirs(final_path, exist_ok=True)
                for item in os.listdir(root_dir):
                    src, dst = os.path.join(root_dir, item), os.path.join(final_path, item)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
                    elif os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)

            self.emit_state(ImportState.IMPORTING, 90, f"{update_name} ({update_size})", True)
            self._cleanup()
            self.emit_state(ImportState.COMPLETED, 100, "", True)
            self.completed_signal.emit()
        except Exception as e:
            if not self.is_canceled:
                self.error_signal.emit(f"Import failed: {str(e)}")
        finally:
            if zf: zf.close()
            if rf: rf.close()
            if szf: szf.close()
            self._cleanup()
            self.quit()

    def _cleanup(self):
        if not self.is_cleaned and os.path.exists(self.temp_path):
            try:
                self.app_data_mgr.manageTempFolder(clean=True, subfolder=os.path.basename(self.temp_path))
                self.is_cleaned = True
            except Exception as e:
                if not self.is_canceled:
                    self._handle_error(f"Cleanup failed: {str(e)}")