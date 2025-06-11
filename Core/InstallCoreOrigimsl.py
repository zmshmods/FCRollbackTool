import os, psutil, shutil, time, rarfile, zipfile, py7zr
from datetime import datetime
from PySide6.QtCore import QThread, Signal
from Core.Initializer import MainDataManager, ConfigManager, GameManager, AppDataManager, NotificationHandler, ErrorHandler
from Core.Logger import logger
from pathlib import Path
from enum import Enum

class InstallState(Enum):
    """Installation state definitions."""
    PREPARING = "Preparing..."
    BACKING_UP_SETTINGS = "Backing up settings folder..."
    BACKING_UP_TITLE_UPDATE = "Backing up current Title Update..."
    EXTRACTING_FILES = "Extracting Files..."
    INSTALLING_SQUADS = "Installing Squads..."
    INSTALLING_FUT_SQUADS = "Installing FutSquads..."
    DELETING_STORED_TITLE_UPDATE = "Deleting Title Update from Profiles..."
    DELETING_SQUAD_FILES = "Deleting Squad Files..."
    DELETING_LIVE_TUNING_UPDATE = "Deleting Live Tuning Update..."
    INSTALLATION_COMPLETED = "Installation Completed!"

class InstallCore(QThread):
    """Manages game update installation in a separate thread."""
    state_changed = Signal(InstallState, int, str)  # Emits state, progress, details
    completed_signal = Signal()
    error_signal = Signal(str)  
    cancel_signal = Signal()
    request_table_update = Signal()  # Signal to request table update after SHA1 update

    def __init__(self, update_name: str, tab_key: str, game_path: str, file_path: str):
        super().__init__()
        self.update_name = update_name
        self.tab_key = tab_key
        self.game_path = game_path
        self.file_path = file_path
        self.is_canceled = False
        self.options = InstallOptions(self, game_path)
        self.game_mgr = GameManager()
        self.app_data_mgr = AppDataManager()
        
    def emit_state(self, state: InstallState, progress: int, details: str = ""):
        """Emit state changes to update UI."""
        if not self.is_canceled:
            try:
                self.state_changed.emit(state, progress, details)
            except Exception as e:
                ErrorHandler.handleError(f"Failed to emit state for {state.value}: {str(e)}")
                self.error_signal.emit(str(e))

    def check_blocking_processes(self) -> bool:
        """Check for processes that block installation."""
        blocking_processes = [
            f"{self.game_mgr.GAME_PREFIX}{version}.exe" for version in self.game_mgr.GAME_VERSION
        ] + ["FIFA Mod Manager.exe", "FIFA Editor Tool.exe", "FMT.exe", "Launcher.exe"]
        
        active_processes = []
        for proc in psutil.process_iter(['name', 'pid', 'exe']):
            try:
                proc_name = proc.info['name'].lower()
                proc_path = proc.info['exe']
                if any(proc_name == block.lower() for block in blocking_processes):
                    if proc_name == "launcher.exe":
                        dll_path = os.path.join(os.path.dirname(proc_path), "FCLiveEditor.DLL")
                        if not os.path.exists(dll_path):
                            continue  # Not FC LE
                    active_processes.append((proc.info['name'], proc.info['pid']))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # If no blocking processes found, proceed
        if not active_processes:
            return True
        
        process_count = len(active_processes)
        is_plural = process_count > 1
        process_list = "\n".join([f"- {name} (PID: {pid})" for name, pid in active_processes])
        message = (
            f"There {'are' if is_plural else 'is'} {'processes' if is_plural else 'process'} "
            f"preventing installation:\n{process_list}\n\n"
            f"Do you want to close {'them' if is_plural else 'it'} and continue?"
        )
        response = NotificationHandler.showConfirmation(message)
        if response == "Yes":
            for _, pid in active_processes:
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    proc.wait(timeout=5)
                    logger.info(f"Terminated process: {pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
                    logger.warning(f"Failed to terminate process {pid}: {str(e)}")
            return True
        else:
            logger.info("Installation canceled due to blocking processes")
            return False
        
    def cancel(self):
        """Cancel the installation process."""
        if not self.is_canceled:
            self.is_canceled = True
            self.cancel_signal.emit()
            logger.info(f"Installation canceled: {self.update_name}")
            self.quit()
            self.wait()  # wait for thread to finish

    def run(self):
        """Execute installation process based on tab_key."""
        try:
            # Check for blocking processes before starting installation
            if not self.check_blocking_processes():
                self.cancel()
                return
            logger.info(f"Starting installation: {self.update_name} for tab {self.tab_key} on game {self.game_path}")
            enabled_options = {
                self.game_mgr.getTabKeyTitleUpdates(): [
                    "BackupSettingsGameFolder", "BackupTitleUpdate", "DeleteStoredTitleUpdate", "DeleteLiveTuningUpdate"
                ],
                self.game_mgr.getTabKeySquadsUpdates(): [
                    "BackupSettingsGameFolder", "DeleteSquadsAfterInstall"
                ],
                self.game_mgr.getTabKeyFutSquadsUpdates(): [
                    "BackupSettingsGameFolder", "DeleteSquadsAfterInstall"
                ]
            }.get(self.tab_key, [])

            self.emit_state(InstallState.PREPARING, 0)

            if "BackupSettingsGameFolder" in enabled_options and not self.is_canceled:
                self.options.backup_game_settings_folder()
            if "BackupTitleUpdate" in enabled_options and not self.is_canceled:
                if not self.options.backup_title_update(self.update_name):
                    logger.info("Installation canceled during backup")
                    self.cancel()
                    return

            if not self.is_canceled:
                # Emit initial install state based on tab_key
                state = (InstallState.EXTRACTING_FILES if self.tab_key == self.game_mgr.getTabKeyTitleUpdates()
                         else InstallState.INSTALLING_SQUADS if self.tab_key == self.game_mgr.getTabKeySquadsUpdates()
                         else InstallState.INSTALLING_FUT_SQUADS)
                self.emit_state(state, 0, os.path.basename(self.file_path))

                install_fn = (self.install_title_update if self.tab_key == self.game_mgr.getTabKeyTitleUpdates()
                              else self.install_squad_update)
                install_fn()

            if not self.is_canceled:
                cleanup_tasks = [
                    ("DeleteLiveTuningUpdate", self.options.delete_live_tuning_update, self.game_path),
                    ("DeleteStoredTitleUpdate", self.options.delete_stored_title_update, self.file_path),
                    ("DeleteSquadsAfterInstall", self.options.delete_squads_after_install, self.file_path)
                ]
                for option, fn, arg in cleanup_tasks:
                    if option in enabled_options and not self.is_canceled:
                        fn(arg)

            if not self.is_canceled:
                self.clean_steam_files()
                self.emit_state(InstallState.INSTALLATION_COMPLETED, 100, "")
                self.completed_signal.emit()
                logger.info(f"Installation completed: {self.update_name}")
        except Exception as e:
            if not self.is_canceled:
                error_msg = f"Installation of {self.update_name} failed: {str(e)}"
                ErrorHandler.handleError(error_msg)
                self.error_signal.emit(error_msg)

    def install_title_update(self):
        """Install Title Update to game directory, handling both compressed and non-compressed files."""
        if self.is_canceled:
            return
        try:
            logger.info(f"Installing Title Update: {self.update_name}")
            config_mgr = ConfigManager()
            main_data_mgr = MainDataManager()
            ext = os.path.splitext(self.file_path)[1].lower()
            is_compressed = ext in main_data_mgr.getCompressedFileExtensions()
            file_path, dest_dir = Path(self.file_path).resolve(), Path(self.game_path).resolve()

            self.emit_state(InstallState.EXTRACTING_FILES, 0, os.path.basename(self.file_path))

            # Define expected executable names dynamically
            expected_exes = [f"{self.game_mgr.GAME_PREFIX}{version}.exe" for version in self.game_mgr.GAME_VERSION]

            if is_compressed:
                # Handle compressed files (.rar, .zip, .7z)
                pwd = main_data_mgr.getKey()
                os.makedirs(dest_dir, exist_ok=True)

                if ext == ".rar":
                    unrar = main_data_mgr.getUnRAR()
                    rarfile.UNRAR_TOOL = unrar
                    with rarfile.RarFile(str(file_path)) as rf:
                        rf.setpassword(pwd)
                        archive_files = [item.filename for item in rf.infolist() if not item.is_dir()]
                        # Find the root directory containing the executable
                        root_dir = None
                        exe_path = None
                        found_exes = []
                        for file in archive_files:
                            if file.lower().endswith('.exe'):
                                found_exes.append(os.path.basename(file))
                            if os.path.basename(file).lower() in [exe.lower() for exe in expected_exes]:
                                exe_path = file
                                root_dir = os.path.dirname(file)
                                logger.debug(f"Found executable: {os.path.basename(file)} at: {file}, root directory: {root_dir}")
                                break
                        if not exe_path:
                            raise ValueError(f"No expected executable ({', '.join(expected_exes)}), Please ensure the archive or folder you want to install it contains the game's executable file")

                        # Filter files to extract (only files within root_dir or root if root_dir is empty)
                        files_to_extract = archive_files if not root_dir else [
                            f for f in archive_files
                            if f.startswith(root_dir + '/') or f == exe_path
                        ]
                        logger.debug(f"Extracting {len(files_to_extract)} files from root directory: {root_dir or 'archive root'}")

                        # Extract files one by one to show progress in UI
                        for i, file in enumerate(files_to_extract):
                            if self.is_canceled:
                                return
                            rel_path = os.path.basename(file) if not root_dir else os.path.relpath(file, root_dir).replace(os.sep, '/')
                            rf.extract(file, path=dest_dir)
                            progress = ((i + 1) / len(files_to_extract)) * 100
                            self.emit_state(InstallState.EXTRACTING_FILES, int(progress), rel_path)
                            logger.debug(f"Extracted: {rel_path}")

                        # Move files from root_dir to dest_dir root if root_dir exists
                        src_root = os.path.join(dest_dir, root_dir) if root_dir else dest_dir
                        parent_folder = os.path.join(dest_dir, root_dir.split('/')[0]) if root_dir else dest_dir
                        if root_dir and os.path.exists(src_root):
                            files = []
                            for root, _, filenames in os.walk(src_root):
                                files.extend(os.path.join(root, fname) for fname in filenames)

                            for src in files:
                                if self.is_canceled:
                                    shutil.rmtree(parent_folder, ignore_errors=True)
                                    return
                                rel_path = os.path.relpath(src, src_root).replace(os.sep, '/')
                                dst = os.path.join(dest_dir, rel_path)
                                os.makedirs(os.path.dirname(dst), exist_ok=True)
                                shutil.move(src, dst)
                                #logger.debug(f"Moved: {rel_path}")

                            # Move directory structure (including empty directories)
                            for root, dirs, _ in os.walk(src_root):
                                for d in dirs:
                                    src_subdir = os.path.join(root, d)
                                    rel_subdir = os.path.relpath(src_subdir, src_root).replace(os.sep, '/')
                                    dst_subdir = os.path.join(dest_dir, rel_subdir)
                                    os.makedirs(dst_subdir, exist_ok=True)
                                    logger.debug(f"Moved directly to game path: {dst_subdir}")

                            # Verify key file exists in dest_dir before removing parent
                            if not os.path.exists(os.path.join(dest_dir, os.path.basename(exe_path))):
                                raise ValueError(f"Failed to move executable {os.path.basename(exe_path)} to {dest_dir}")

                            # Remove the parent folder
                            shutil.rmtree(parent_folder, ignore_errors=True)
                            logger.debug(f"Removed parent folder: {parent_folder}")

                elif ext == ".zip":
                    with zipfile.ZipFile(str(file_path), 'r') as zf:
                        if pwd:
                            zf.setpassword(pwd.encode('utf-8'))
                        archive_files = [item.filename for item in zf.infolist() if not item.is_dir()]
                        # Find the root directory containing the executable
                        root_dir = None
                        exe_path = None
                        found_exes = []
                        for file in archive_files:
                            if file.lower().endswith('.exe'):
                                found_exes.append(os.path.basename(file))
                            if os.path.basename(file).lower() in [exe.lower() for exe in expected_exes]:
                                exe_path = file
                                root_dir = os.path.dirname(file)
                                logger.debug(f"Found executable: {os.path.basename(file)} at: {file}, root directory: {root_dir}")
                                break
                        if not exe_path:
                            raise ValueError(f"No expected executable ({', '.join(expected_exes)}), Please ensure the archive or folder you want to install it contains the game's executable file")

                        # Filter files to extract (only files within root_dir or root if root_dir is empty)
                        files_to_extract = archive_files if not root_dir else [
                            f for f in archive_files
                            if f.startswith(root_dir + '/') or f == exe_path
                        ]
                        logger.debug(f"Extracting {len(files_to_extract)} files from root directory: {root_dir or 'archive root'}")

                        for i, file in enumerate(files_to_extract):
                            if self.is_canceled:
                                return
                            rel_path = os.path.basename(file) if not root_dir else os.path.relpath(file, root_dir).replace(os.sep, '/')
                            zf.extract(file, path=dest_dir)
                            progress = ((i + 1) / len(files_to_extract)) * 100
                            self.emit_state(InstallState.EXTRACTING_FILES, int(progress), rel_path)
                            logger.debug(f"Extracted: {rel_path}")

                        # Move files from root_dir to dest_dir root if root_dir exists
                        src_root = os.path.join(dest_dir, root_dir) if root_dir else dest_dir
                        parent_folder = os.path.join(dest_dir, root_dir.split('/')[0]) if root_dir else dest_dir
                        if root_dir and os.path.exists(src_root):
                            files = []
                            for root, _, filenames in os.walk(src_root):
                                files.extend(os.path.join(root, fname) for fname in filenames)

                            for src in files:
                                if self.is_canceled:
                                    shutil.rmtree(parent_folder, ignore_errors=True)
                                    return
                                rel_path = os.path.relpath(src, src_root).replace(os.sep, '/')
                                dst = os.path.join(dest_dir, rel_path)
                                os.makedirs(os.path.dirname(dst), exist_ok=True)
                                shutil.move(src, dst)
                                logger.debug(f"Moved: {rel_path}")

                            # Move directory structure (including empty directories)
                            for root, dirs, _ in os.walk(src_root):
                                for d in dirs:
                                    src_subdir = os.path.join(root, d)
                                    rel_subdir = os.path.relpath(src_subdir, src_root).replace(os.sep, '/')
                                    dst_subdir = os.path.join(dest_dir, rel_subdir)
                                    os.makedirs(dst_subdir, exist_ok=True)
                                    logger.debug(f"Created directory: {dst_subdir}")

                            # Verify key file exists in dest_dir before removing parent
                            if not os.path.exists(os.path.join(dest_dir, os.path.basename(exe_path))):
                                raise ValueError(f"Failed to move executable {os.path.basename(exe_path)} to {dest_dir}")

                            # Remove the parent folder
                            shutil.rmtree(parent_folder, ignore_errors=True)
                            logger.debug(f"Removed parent folder: {parent_folder}")

                elif ext == ".7z":
                    with py7zr.SevenZipFile(str(file_path), 'r', password=pwd) as szf:
                        archive_files = [name for name in szf.getnames() if not name.endswith('/')]
                        # Find the root directory containing the executable
                        root_dir = None
                        exe_path = None
                        found_exes = []
                        for file in archive_files:
                            if file.lower().endswith('.exe'):
                                found_exes.append(os.path.basename(file))
                            if os.path.basename(file).lower() in [exe.lower() for exe in expected_exes]:
                                exe_path = file
                                root_dir = os.path.dirname(file)
                                logger.debug(f"Found executable: {os.path.basename(file)} at: {file}, root directory: {root_dir}")
                                break
                        if not exe_path:
                            raise ValueError(f"No expected executable ({', '.join(expected_exes)}), Please ensure the archive or folder you want to install it contains the game's executable file")

                        # Filter files to extract (only files within root_dir or root if root_dir is empty)
                        files_to_extract = archive_files if not root_dir else [
                            f for f in archive_files
                            if f.startswith(root_dir + '/') or f == exe_path
                        ]
                        logger.debug(f"Extracting {len(files_to_extract)} files from root directory: {root_dir or 'archive root'}")

                        # Extract files one by one to show progress in UI
                        for i, file in enumerate(files_to_extract):
                            if self.is_canceled:
                                return
                            rel_path = os.path.basename(file) if not root_dir else os.path.relpath(file, root_dir).replace(os.sep, '/')
                            szf.extract(targets=[file], path=dest_dir)
                            progress = ((i + 1) / len(files_to_extract)) * 100
                            self.emit_state(InstallState.EXTRACTING_FILES, int(progress), rel_path)
                            logger.debug(f"Extracted: {rel_path}")

                        # Move files from root_dir to dest_dir root if root_dir exists
                        src_root = os.path.join(dest_dir, root_dir) if root_dir else dest_dir
                        parent_folder = os.path.join(dest_dir, root_dir.split('/')[0]) if root_dir else dest_dir
                        if root_dir and os.path.exists(src_root):
                            files = []
                            for root, _, filenames in os.walk(src_root):
                                files.extend(os.path.join(root, fname) for fname in filenames)

                            for src in files:
                                if self.is_canceled:
                                    shutil.rmtree(parent_folder, ignore_errors=True)
                                    return
                                rel_path = os.path.relpath(src, src_root).replace(os.sep, '/')
                                dst = os.path.join(dest_dir, rel_path)
                                os.makedirs(os.path.dirname(dst), exist_ok=True)
                                shutil.move(src, dst)
                                logger.debug(f"Moved: {rel_path}")

                            # Move directory structure (including empty directories)
                            for root, dirs, _ in os.walk(src_root):
                                for d in dirs:
                                    src_subdir = os.path.join(root, d)
                                    rel_subdir = os.path.relpath(src_subdir, src_root).replace(os.sep, '/')
                                    dst_subdir = os.path.join(dest_dir, rel_subdir)
                                    os.makedirs(dst_subdir, exist_ok=True)
                                    logger.debug(f"Created directory: {dst_subdir}")

                            # Verify key file exists in dest_dir before removing parent
                            if not os.path.exists(os.path.join(dest_dir, os.path.basename(exe_path))):
                                raise ValueError(f"Failed to move executable {os.path.basename(exe_path)} to {dest_dir}")

                            # Remove the parent folder
                            shutil.rmtree(parent_folder, ignore_errors=True)
                            logger.debug(f"Removed parent folder: {parent_folder}")

                else:
                    raise ValueError(f"Unsupported file extension: {ext}")

                logger.info(f"Extracted and moved compressed file contents to {dest_dir}")

            else:
                # Handle non-compressed folder
                src_dir = file_path
                # Find the root directory containing the executable
                root_dir = None
                found_exes = []
                for root, _, files in os.walk(src_dir):
                    for file in files:
                        if file.lower().endswith('.exe'):
                            found_exes.append(file)
                        if file.lower() in [exe.lower() for exe in expected_exes]:
                            root_dir = root
                            logger.debug(f"Found executable: {file} in: {root_dir}")
                            break
                    if root_dir:
                        break
                if not root_dir:
                    raise ValueError(f"No expected executable ({', '.join(expected_exes)}) found in source folder. Found: {', '.join(found_exes) if found_exes else 'none'}")

                files = []
                for root, _, filenames in os.walk(root_dir):
                    files.extend(os.path.join(root, fname) for fname in filenames)

                # Copy files with directory structure
                for i, src in enumerate(files):
                    if self.is_canceled:
                        return
                    rel_path = os.path.relpath(src, root_dir).replace(os.sep, '/')
                    dst = os.path.join(dest_dir, rel_path)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    progress = ((i + 1) / len(files)) * 100
                    self.emit_state(InstallState.EXTRACTING_FILES, int(progress), rel_path)
                    logger.debug(f"Copied: {rel_path}")

                # Copy directory structure (including empty directories)
                for root, dirs, _ in os.walk(root_dir):
                    for d in dirs:
                        src_subdir = os.path.join(root, d)
                        rel_subdir = os.path.relpath(src_subdir, root_dir).replace(os.sep, '/')
                        dst_subdir = os.path.join(dest_dir, rel_subdir)
                        os.makedirs(dst_subdir, exist_ok=True)
                        logger.debug(f"Created directory: {dst_subdir}")

                logger.info(f"Title Update copied to {dest_dir}")

            # Ensure contents are directly in dest_dir (no subfolder)
            root_dir_name = os.path.basename(root_dir) if root_dir else ''
            subfolder_path = os.path.join(dest_dir, root_dir_name) if root_dir_name else ''
            if subfolder_path and os.path.exists(subfolder_path) and os.path.isdir(subfolder_path):
                logger.debug(f"Found subfolder {root_dir_name} in {dest_dir}, moving contents to root")
                for item in os.listdir(subfolder_path):
                    if self.is_canceled:
                        shutil.rmtree(subfolder_path, ignore_errors=True)
                        return
                    src_item = os.path.join(subfolder_path, item)
                    dst_item = os.path.join(dest_dir, item)
                    if os.path.exists(dst_item):
                        if os.path.isdir(dst_item):
                            shutil.rmtree(dst_item, ignore_errors=True)
                        else:
                            os.remove(dst_item)
                    shutil.move(src_item, dst_item)
                    logger.debug(f"Moved: {item} to {dest_dir}")
                shutil.rmtree(subfolder_path, ignore_errors=True)
                logger.debug(f"Removed subfolder: {subfolder_path}")

            # Validate and update SHA1
            if not self.is_canceled:
                if not self.game_mgr.validateAndUpdateGameExeSHA1(self.game_path, config_mgr):
                    error_msg = f"Failed to update SHA1 for game {self.game_path}"
                    ErrorHandler.handleError(error_msg)
                    self.error_signal.emit(error_msg)
                else:
                    self.request_table_update.emit()
                    logger.debug("Requested table update after SHA1 validation")

            if not self.is_canceled:
                logger.info("Title Update installed successfully")
                self.emit_state(InstallState.INSTALLATION_COMPLETED, 100, "")
                self.completed_signal.emit()
        except Exception as e:
            ErrorHandler.handleError(f"Failed to install Title Update {self.update_name}: {str(e)}")
            self.error_signal.emit(str(e))
            if not self.is_canceled:
                self.cancel()

    def install_squad_update(self):
        """Install squad/fut update to game settings folder, handling both compressed and non-compressed files."""
        if self.is_canceled:
            return
        try:
            logger.info(f"Installing Squad Update: {self.update_name}")
            state = (InstallState.INSTALLING_SQUADS if self.tab_key == self.game_mgr.getTabKeySquadsUpdates()
                     else InstallState.INSTALLING_FUT_SQUADS)
            dst_path = self.game_mgr.getGameSettingsFolderPath(self.game_path)
            main_data_mgr = MainDataManager()
            ext = os.path.splitext(self.file_path)[1].lower()
            is_compressed = ext in main_data_mgr.getCompressedFileExtensions()
            file_path = Path(self.file_path).resolve()

            self.emit_state(state, 0, os.path.basename(self.file_path))
            time.sleep(0.5)  # For UI state

            if is_compressed:
                # Handle compressed files (.rar, .zip, .7z)
                pwd = main_data_mgr.getKey()
                os.makedirs(dst_path, exist_ok=True)

                if ext == ".rar":
                    unrar = main_data_mgr.getUnRAR()
                    rarfile.UNRAR_TOOL = unrar
                    with rarfile.RarFile(str(file_path)) as rf:
                        rf.setpassword(pwd)
                        file_list = [item for item in rf.infolist() if not item.is_dir()]
                        for i, member in enumerate(file_list):
                            if self.is_canceled:
                                return
                            rf.extract(member, dst_path)
                            progress = ((i + 1) / len(file_list)) * 100
                            self.emit_state(state, int(progress), member.filename.replace('\\', '/'))
                            logger.debug(f"Extracted: {member.filename}")
                elif ext == ".zip":
                    with zipfile.ZipFile(str(file_path), 'r') as zf:
                        if pwd:
                            zf.setpassword(pwd.encode('utf-8'))
                        file_list = [item for item in zf.infolist() if not item.is_dir()]
                        for i, member in enumerate(file_list):
                            if self.is_canceled:
                                return
                            zf.extract(member, dst_path)
                            progress = ((i + 1) / len(file_list)) * 100
                            self.emit_state(state, int(progress), member.filename.replace('\\', '/'))
                            logger.debug(f"Extracted: {member.filename}")
                elif ext == ".7z":
                    with py7zr.SevenZipFile(str(file_path), 'r', password=pwd) as szf:
                        file_list = [name for name in szf.getnames() if not name.endswith('/')]
                        for i, member in enumerate(file_list):
                            if self.is_canceled:
                                return
                            szf.extract(path=dst_path, targets=[member])
                            progress = ((i + 1) / len(file_list)) * 100
                            self.emit_state(state, int(progress), member.replace('\\', '/'))
                            logger.debug(f"Extracted: {member}")
                else:
                    raise ValueError(f"Unsupported file extension: {ext}")

                logger.info(f"Extracted squad file to {dst_path}")
            else:
                # Handle non-compressed file
                dst_file = os.path.join(dst_path, os.path.basename(self.file_path))
                shutil.copy2(self.file_path, dst_file)
                self.emit_state(state, 100, os.path.basename(self.file_path))
                logger.info(f"Installed squad file: {dst_file}")

        except Exception as e:
            ErrorHandler.handleError(f"Failed to install Squad Update {self.update_name}: {str(e)}")
            self.error_signal.emit(str(e))

    def clean_steam_files(self):
        """Delete Steam-related files if the game is not from Steam to avoid compatibility issues."""
        if not self.is_canceled and "steam" not in self.game_path.lower():
            logger.info(f"Non-Steam game detected in path: {self.game_path}, cleaning Steam-related files...")
            files_to_delete = [
                os.path.join(self.game_path, "steam_appid.txt"),
                os.path.join(self.game_path, "EAStore.ini")
            ]
            # all .vdf files in game_path
            for file in os.listdir(self.game_path):
                if file.lower().endswith(".vdf"):
                    files_to_delete.append(os.path.join(self.game_path, file))
            
            for file_path in files_to_delete:
                self.options._common_delete(file_path)

class InstallOptions:
    """Handles pre/post-installation tasks."""
    def __init__(self, install_core, game_path: str):
        self.install_core = install_core
        self.game_path = game_path
        self.config_mgr = ConfigManager()
        self.game_mgr = GameManager()
        self.app_data_mgr = AppDataManager()

    def backup_game_settings_folder(self):
        """Backup game settings folder to compressed archive with confirmation."""
        if self.install_core.is_canceled:
            return
        try:
            if not self.config_mgr.getConfigKeyBackupGameSettingsFolder():
                return
            settings_path = self.game_mgr.getGameSettingsFolderPath(self.game_path)
            logger.info("Backing up game settings folder")
            if not os.path.exists(settings_path):
                logger.warning(f"Settings folder not found: {settings_path}")
                return
            
            backup_dir = os.path.join(
                self.app_data_mgr.getDataFolder(), 
                "Backups", 
                self.game_mgr.getShortGameName(self.game_path)
            )
            os.makedirs(backup_dir, exist_ok=True)
            backup_file = os.path.join(backup_dir, f"settings{datetime.now().strftime('%Y-%m-%d')}.zip")

            self.install_core.emit_state(InstallState.BACKING_UP_SETTINGS, 0, os.path.basename(backup_file))
            time.sleep(0.5)  # For UI state

            if os.path.exists(backup_file):
                confirmation_message = (
                    f"\"Backup game settings folder\" option is enabled.\n\n"
                    f"A backup file already exists for today at:\n\"{backup_file}\"\n\n"
                    f"Do you want to replace it?"
                )
                response = NotificationHandler.showConfirmation(confirmation_message)
                if response == "Yes":
                    os.remove(backup_file)
                    logger.info(f"Deleted existing backup file: {backup_file}")
                elif response == "No":
                    logger.info("Backup operation skipped by user")
                    return
                elif response == "Cancel":
                    logger.info("Backup operation canceled by user")
                    self.install_core.cancel()
                    return

            shutil.make_archive(backup_file[:-4], "zip", settings_path)
            self.install_core.emit_state(InstallState.BACKING_UP_SETTINGS, 100, "100%")
            time.sleep(0.5)  # For UI state
            logger.info(f"Settings folder backed up: {backup_file}")
        except Exception as e:
            ErrorHandler.handleError(f"Failed to backup game settings folder for {self.game_path}: {str(e)}")
            self.install_core.error_signal.emit(str(e))

    def backup_title_update(self, update_name: str) -> bool:
        """Backup current Title Update to Profiles, excluding specified folders."""
        if self.install_core.is_canceled:
            return False
        try:
            if not self.config_mgr.getConfigKeyBackupTitleUpdate():
                return True
            update = self.game_mgr.getInstalledCurrentTitleUpdate(self.config_mgr)
            installed_update = update.get(self.game_mgr.getTitleUpdateNameKey(), "Unknown Update") if update else "Unknown Update"
            self.install_core.emit_state(InstallState.BACKING_UP_TITLE_UPDATE, 0, installed_update)
            time.sleep(0.5)  # For UI state
            logger.info(f"Backing up Title Update: {installed_update}")

            full_backup_dir = os.path.join(
                self.game_mgr.getProfileDirectory(
                    self.game_mgr.getShortGameName(self.game_path),
                    self.game_mgr.getProfileTypeTitleUpdate()
                ),
                installed_update
            )

            compressed_extensions = MainDataManager().getCompressedFileExtensions()
            conflict_exists = (os.path.exists(full_backup_dir) or
                              any(os.path.exists(f"{full_backup_dir}{ext}") for ext in compressed_extensions))

            if conflict_exists:
                display_name = full_backup_dir
                for ext in compressed_extensions:
                    if os.path.exists(f"{full_backup_dir}{ext}"):
                        display_name = f"{full_backup_dir}{ext}"
                        break
                confirmation_message = (
                    f"\"Backup current title update\" option is enabled.\n\n"
                    f"A folder or compressed file already exists at:\n\"{display_name}\"\n\n"
                    f"Do you want to replace it?"
                )
                response = NotificationHandler.showConfirmation(confirmation_message)
                if response == "Yes":
                    if os.path.exists(full_backup_dir):
                        shutil.rmtree(full_backup_dir)
                        logger.info(f"Deleted existing backup folder: {full_backup_dir}")
                    for ext in compressed_extensions:
                        compressed_path = f"{full_backup_dir}{ext}"
                        if os.path.exists(compressed_path):
                            os.remove(compressed_path)
                            logger.info(f"Deleted existing compressed file: {compressed_path}")
                elif response == "No":
                    logger.info("Backup operation skipped by user")
                    return True
                elif response == "Cancel":
                    logger.info("Backup operation canceled by user")
                    self.install_core.cancel()
                    return False

            os.makedirs(full_backup_dir, exist_ok=True)
            logger.info(f"Created backup directory: {full_backup_dir}")

            # Collect all files to track progress
            files = []
            exclude_folders = ['Data', 'FIFAModData']
            for root, dirs, filenames in os.walk(self.game_path):
                dirs[:] = [d for d in dirs if d.lower() not in [f.lower() for f in exclude_folders] and not d.lower().startswith('original_')]
                files.extend(os.path.join(root, fname) for fname in filenames)

            # Copy files with directory structure
            for i, src in enumerate(files):
                if self.install_core.is_canceled:
                    return False
                rel_path = os.path.relpath(src, self.game_path).replace(os.sep, '/')
                dst = os.path.join(full_backup_dir, rel_path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                progress = ((i + 1) / len(files)) * 100
                self.install_core.emit_state(InstallState.BACKING_UP_TITLE_UPDATE, int(progress), f"{int(progress)}%")

            # Copy directory structure (including empty directories)
            for root, dirs, _ in os.walk(self.game_path):
                dirs[:] = [d for d in dirs if d.lower() not in [f.lower() for f in exclude_folders] and not d.lower().startswith('original_')]
                for d in dirs:
                    src_subdir = os.path.join(root, d)
                    rel_subdir = os.path.relpath(src_subdir, self.game_path).replace(os.sep, '/')
                    dst_subdir = os.path.join(full_backup_dir, rel_subdir)
                    os.makedirs(dst_subdir, exist_ok=True)

            logger.info(f"Title Update backed up to {full_backup_dir}")
            return True
        except Exception as e:
            ErrorHandler.handleError(f"Failed to backup Title Update {update_name}: {str(e)}")
            self.install_core.error_signal.emit(str(e))
            return False

    def delete_stored_title_update(self, path: str):
        """Delete stored Title Update after installation from Profiles."""
        if self.install_core.is_canceled:
            return
        try:
            if not self.config_mgr.getConfigKeyDeleteStoredTitleUpdate():
                return
            simplified_path = f"Profiles/{os.path.basename(path)}"
            self.install_core.emit_state(InstallState.DELETING_STORED_TITLE_UPDATE, 0, simplified_path)
            self._common_delete(path)
            time.sleep(0.5)  # For UI state
        except Exception as e:
            ErrorHandler.handleError(f"Failed to delete stored Title Update {path}: {str(e)}")
            self.install_core.error_signal.emit(str(e))

    def delete_squads_after_install(self, path: str):
        """Delete squads files after installation from Profiles."""
        if self.install_core.is_canceled:
            return
        try:
            if not self.config_mgr.getConfigKeyDeleteSquadsAfterInstall():
                return
            simplified_path = f"Profiles/{os.path.basename(path)}"
            self.install_core.emit_state(InstallState.DELETING_SQUAD_FILES, 0, simplified_path)
            self._common_delete(path)
            time.sleep(0.5)  # For UI state
        except Exception as e:
            ErrorHandler.handleError(f"Failed to delete squad files {path}: {str(e)}")
            self.install_core.error_signal.emit(str(e))

    def delete_live_tuning_update(self, game_path: str):
        """Delete live tuning update folder."""
        if self.install_core.is_canceled:
            return
        try:
            if not self.config_mgr.getConfigKeyDeleteLiveTuningUpdate():
                return
            path = self.game_mgr.getLiveTuningUpdateFilePath(game_path)
            self.install_core.emit_state(InstallState.DELETING_LIVE_TUNING_UPDATE, 0, path)
            self._common_delete(path)
            time.sleep(0.5)  # For UI state
        except Exception as e:
            ErrorHandler.handleError(f"Failed to delete live tuning update for {game_path}: {str(e)}")
            self.install_core.error_signal.emit(str(e))

    def _common_delete(self, path: str):
        """Delete file or directory."""
        try:
            if os.path.exists(path):
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)
                logger.info(f"Resource deleted: {path}")
        except Exception as e:
            ErrorHandler.handleError(f"Failed to delete resource {path}: {str(e)}")
            self.install_core.error_signal.emit(str(e))