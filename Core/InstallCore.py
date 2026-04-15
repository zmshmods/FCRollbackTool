import os, psutil, shutil, time, subprocess, ctypes, sys, re
from datetime import datetime
from PySide6.QtCore import QThread, Signal
from pathlib import Path
from enum import Enum

from Core.Logger import logger
from Core.MainDataManager import MainDataManager
from Core.ConfigManager import ConfigManager
from Core.GameManager import GameManager
from Core.AppDataManager import AppDataManager
from Core.NotificationManager import NotificationHandler
from Core.ErrorHandler import ErrorHandler


class InstallState(Enum):
    """Installation state definitions."""

    PREPARING = "Preparing..."
    BACKING_UP_SETTINGS = "Backing up settings folder..."
    BACKING_UP_TITLE_UPDATE = "Backing up current Title Update..."
    INSTALLING_FILES = "Installing Files..."
    INSTALLING_SQUADS = "Installing Squads..."
    INSTALLING_FUT_SQUADS = "Installing FutSquads..."
    DELETING_STORED_TITLE_UPDATE = "Deleting Title Update from Profiles..."
    DELETING_SQUAD_FILES = "Deleting Squad Files..."
    DELETING_LIVE_TUNING_UPDATE = "Deleting Live Tuning Update..."
    INSTALLATION_COMPLETED = "Installation Completed!"


class InstallCore(QThread):
    """Manages game update installation in a separate thread."""

    state_changed = Signal(InstallState, int, str)
    completed_signal = Signal()
    error_signal = Signal(str)
    cancel_signal = Signal()
    request_table_update = Signal()

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
                ErrorHandler.handleError(
                    f"Failed to emit state for {state.value}: {str(e)}"
                )
                self.error_signal.emit(str(e))

    def check_blocking_processes(self) -> bool:
        """Check for processes that block installation."""
        game_executables = [
            p.exe_name for p in self.game_mgr.profile_manager.get_all_profiles()
        ]
        blocking_processes = game_executables + [
            "FIFA Mod Manager.exe",
            "FIFA Editor Tool.exe",
            "FMT.exe",
            "Launcher.exe",
        ]

        active_processes = []
        for proc in psutil.process_iter(["name", "pid", "exe"]):
            try:
                proc_name = proc.info["name"].lower()
                proc_path = proc.info["exe"]
                if any(proc_name == block.lower() for block in blocking_processes):
                    if proc_name == "launcher.exe":
                        dll_path = os.path.join(
                            os.path.dirname(proc_path), "FCLiveEditor.DLL"
                        )
                        if not os.path.exists(dll_path):
                            continue
                    active_processes.append((proc.info["name"], proc.info["pid"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not active_processes:
            return True

        process_count = len(active_processes)
        is_plural = process_count > 1
        process_list = "\n".join(
            [f"- {name} (PID: {pid})" for name, pid in active_processes]
        )
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
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.TimeoutExpired,
                ) as e:
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
            self.wait()

    def ensure_admin_privileges(self):
        """Check for admin privileges by attempting to write a temp file. Raises error if needed."""
        from pathlib import Path
        import os

        dest_dir = str(Path(self.game_path).resolve())
        if not os.path.exists(dest_dir):
            return  # Later methods will fail natively if dir doesn't exist

        try:
            test_file = os.path.join(dest_dir, ".admin_tmp")
            with open(test_file, "w") as f:
                f.write("1")
            os.remove(test_file)
        except PermissionError:
            logger.warning(f"Permission denied to write to {dest_dir}")

            folder_name = os.path.basename(os.path.dirname(dest_dir))
            error_msg = (
                f"Access denied to the directory:\n{dest_dir}\n\n"
                f"To resolve this, run the tool as an Administrator\n"
                f'or move your game folder outside of the "{folder_name}" folder.'
            )
            raise PermissionError(error_msg)

    def run(self):
        """Execute installation process based on tab_key."""
        try:
            if self.tab_key == self.game_mgr.getTabKeyTitleUpdates():
                self.ensure_admin_privileges()
                if self.is_canceled:
                    return

                if not self.check_blocking_processes():
                    self.cancel()
                    return

            logger.info(
                f"Starting installation: {self.update_name} for tab {self.tab_key} on game {self.game_path}"
            )
            enabled_options = {
                self.game_mgr.getTabKeyTitleUpdates(): [
                    "BackupSettingsGameFolder",
                    "BackupTitleUpdate",
                    "DeleteStoredTitleUpdate",
                    "DeleteLiveTuningUpdate",
                ],
                self.game_mgr.getTabKeySquadsUpdates(): [
                    "BackupSettingsGameFolder",
                    "DeleteSquadsAfterInstall",
                ],
                self.game_mgr.getTabKeyFutSquadsUpdates(): [
                    "BackupSettingsGameFolder",
                    "DeleteSquadsAfterInstall",
                ],
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
                state = (
                    InstallState.INSTALLING_FILES
                    if self.tab_key == self.game_mgr.getTabKeyTitleUpdates()
                    else InstallState.INSTALLING_SQUADS
                    if self.tab_key == self.game_mgr.getTabKeySquadsUpdates()
                    else InstallState.INSTALLING_FUT_SQUADS
                )
                self.emit_state(state, 0, os.path.basename(self.file_path))

                install_fn = (
                    self.install_title_update
                    if self.tab_key == self.game_mgr.getTabKeyTitleUpdates()
                    else self.install_squad_update
                )
                install_fn()

            if not self.is_canceled:
                cleanup_tasks = [
                    (
                        "DeleteLiveTuningUpdate",
                        self.options.delete_live_tuning_update,
                        self.game_path,
                    ),
                    (
                        "DeleteStoredTitleUpdate",
                        self.options.delete_stored_title_update,
                        self.file_path,
                    ),
                    (
                        "DeleteSquadsAfterInstall",
                        self.options.delete_squads_after_install,
                        self.file_path,
                    ),
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

    def delete_existing_file(self, file_path: str):
        """Delete existing file or directory before installation."""
        if os.path.exists(file_path):
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    logger.debug(f"Deleted existing directory: {file_path}")
                else:
                    os.remove(file_path)
                    logger.debug(f"Deleted existing file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {str(e)}")

    def install_title_update(self):
        """Install Title Update to game directory, handling both compressed and non-compressed files."""
        if self.is_canceled:
            return
        try:
            logger.info(f"Installing Title Update: {self.update_name}")
            config_mgr = ConfigManager()
            main_data_mgr = MainDataManager()
            game_id = self.game_mgr.getSelectedGameId(self.game_path)
            ext = os.path.splitext(self.file_path)[1].lower()
            is_compressed = ext in main_data_mgr.getCompressedFileExtensions()
            file_path, dest_dir = (
                Path(self.file_path).resolve(),
                Path(self.game_path).resolve(),
            )

            if not os.path.exists(dest_dir):
                raise FileNotFoundError(
                    f"Game directory not found, cannot install update. Path does not exist: {dest_dir}"
                )

            # Clean the destination directory

            # Clean the destination directory
            match game_id:
                case "FC24":
                    logger.info(
                        "Detected FC24. Only deleting files that have matching counterparts."
                    )
                case _:  # Default case
                    logger.info(
                        f"Cleaning game directory before install (Game: {game_id}): {dest_dir}"
                    )
                    data_folder_name_lower = "data"
                    steam_related_exclusions = ["steam_appid.txt", "eastore.ini"]
                    for file in os.listdir(dest_dir):
                        if file.lower().endswith(".vdf"):
                            steam_related_exclusions.append(file.lower())
                    try:
                        for item_name in os.listdir(dest_dir):
                            if self.is_canceled:
                                return

                            if (
                                item_name.lower() == data_folder_name_lower
                                or item_name.lower() in steam_related_exclusions
                            ):
                                logger.debug(f"Skipping deletion of: {item_name}")
                                continue

                            item_path = os.path.join(dest_dir, item_name)

                            try:
                                if os.path.isdir(item_path):
                                    shutil.rmtree(item_path)
                                    logger.debug(f"Deleted directory: {item_path}")
                                elif os.path.isfile(item_path):
                                    os.remove(item_path)
                                    logger.debug(f"Deleted file: {item_path}")
                            except PermissionError as pe:
                                logger.error(
                                    f"Permission error while cleaning {item_path}: {str(pe)}"
                                )
                                raise pe
                            except Exception as e:
                                logger.warning(
                                    f"Failed to delete {item_path} during pre-install clean: {str(e)}"
                                )

                    except Exception as e:
                        logger.error(
                            f"Failed during pre-install cleaning of {dest_dir}: {str(e)}"
                        )
                        raise e

            self.emit_state(
                InstallState.INSTALLING_FILES, 0, os.path.basename(self.file_path)
            )

            expected_exes = [
                p.exe_name for p in self.game_mgr.profile_manager.get_all_profiles()
            ]

            if is_compressed:
                pwd = main_data_mgr.getKey()
                os.makedirs(dest_dir, exist_ok=True)

                seven_z = main_data_mgr.get7z()
                if not os.path.exists(seven_z):
                    raise FileNotFoundError(f"7z tool not found at: {seven_z}")

                list_cmd = [seven_z, "l", "-ba", "-slt", str(file_path)]
                if pwd:
                    list_cmd.insert(2, f"-p{pwd}")

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                result = subprocess.run(
                    list_cmd, capture_output=True, text=True, startupinfo=startupinfo
                )

                archive_files = []
                current_path = None
                is_dir = False
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("Path = "):
                        current_path = line[7:]
                        is_dir = False
                    elif line.startswith("Attributes = "):
                        if "D" in line[13:]:
                            is_dir = True
                    elif line == "":
                        if current_path and not is_dir:
                            archive_files.append(current_path.replace("\\", "/"))
                        current_path = None

                root_dir = None
                exe_path = None
                found_exes = []
                for file in archive_files:
                    if file.lower().endswith(".exe"):
                        found_exes.append(os.path.basename(file))
                    if os.path.basename(file).lower() in [
                        exe.lower() for exe in expected_exes
                    ]:
                        exe_path = file
                        root_dir = os.path.dirname(file)
                        logger.debug(
                            f"Found executable: {os.path.basename(file)} at: {file}, root directory: {root_dir}"
                        )
                        break

                if not exe_path:
                    raise ValueError(
                        f"No expected executable ({', '.join(expected_exes)}), Please ensure the archive or folder you want to install it contains the game's executable file"
                    )

                files_to_extract = (
                    archive_files
                    if not root_dir
                    else [
                        f
                        for f in archive_files
                        if f.startswith(root_dir + "/") or f == exe_path
                    ]
                )
                logger.debug(
                    f"Extracting {len(files_to_extract)} files from root directory: {root_dir or 'archive root'}"
                )

                delete_targets = []
                for file in files_to_extract:
                    rel_path = (
                        file.replace(os.sep, "/")
                        if not root_dir
                        else os.path.relpath(file, root_dir).replace(os.sep, "/")
                    )
                    final_dest = os.path.join(dest_dir, rel_path)
                    delete_targets.append(final_dest)
                for d in delete_targets:
                    self.delete_existing_file(d)

                list_file_path = os.path.join(
                    self.app_data_mgr.getTempFolder(),
                    f"extract_list_{os.path.basename(file_path)}.txt",
                )
                os.makedirs(os.path.dirname(list_file_path), exist_ok=True)
                with open(list_file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(files_to_extract))

                extract_cmd = [
                    seven_z,
                    "x",
                    str(file_path),
                    f"-o{dest_dir}",
                    f"@{list_file_path}",
                    "-y",
                    "-bb3",
                    "-bsp1",
                    "-scsUTF-8",
                ]
                if pwd:
                    extract_cmd.insert(2, f"-p{pwd}")

                process = subprocess.Popen(
                    extract_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    startupinfo=startupinfo,
                )

                current_progress = 0
                current_file = ""

                display_file = "Extracting..."
                if process.stdout:
                    for line in process.stdout:
                        if self.is_canceled:
                            process.terminate()
                            return

                        output = line.strip()
                        file_match = re.match(r"^(?:-\s|Extracting\s+)(.+)$", output)
                        if file_match:
                            filename = file_match.group(1).strip()
                            if filename:
                                current_file = filename.replace("\\", "/")
                                display_file = current_file

                                if root_dir:
                                    top_folder = root_dir.split("/")[0] + "/"
                                    if current_file.lower().startswith(
                                        top_folder.lower()
                                    ):
                                        display_file = current_file[len(top_folder) :]

                                self.emit_state(
                                    InstallState.INSTALLING_FILES,
                                    current_progress,
                                    display_file,
                                )

                        elif "%" in output:
                            pct_match = re.search(r"(\d+)%", output)
                            if pct_match:
                                current_progress = int(pct_match.group(1))
                                self.emit_state(
                                    InstallState.INSTALLING_FILES,
                                    current_progress,
                                    display_file,
                                )

                process.wait()

                if os.path.exists(list_file_path):
                    os.remove(list_file_path)

                src_root = os.path.join(dest_dir, root_dir) if root_dir else dest_dir
                parent_folder = (
                    os.path.join(dest_dir, root_dir.split("/")[0])
                    if root_dir
                    else dest_dir
                )

                if root_dir and os.path.exists(src_root):
                    files = []
                    for root, _, filenames in os.walk(src_root):
                        files.extend(os.path.join(root, fname) for fname in filenames)

                    dst_list = []
                    for src in files:
                        rel_path = os.path.relpath(src, src_root).replace(os.sep, "/")
                        dst = os.path.join(dest_dir, rel_path)
                        dst_list.append(dst)
                    for d in dst_list:
                        self.delete_existing_file(d)

                    for src in files:
                        if self.is_canceled:
                            shutil.rmtree(parent_folder, ignore_errors=True)
                            return
                        rel_path = os.path.relpath(src, src_root).replace(os.sep, "/")
                        dst = os.path.join(dest_dir, rel_path)

                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.move(src, dst)
                        logger.debug(f"Moved: {rel_path}")

                    for root, dirs, _ in os.walk(src_root):
                        for d in dirs:
                            src_subdir = os.path.join(root, d)
                            rel_subdir = os.path.relpath(src_subdir, src_root).replace(
                                os.sep, "/"
                            )
                            dst_subdir = os.path.join(dest_dir, rel_subdir)
                            os.makedirs(dst_subdir, exist_ok=True)

                    if not os.path.exists(
                        os.path.join(dest_dir, os.path.basename(exe_path))
                    ):
                        raise ValueError(
                            f"Failed to move executable {os.path.basename(exe_path)} to {dest_dir}"
                        )

                    shutil.rmtree(parent_folder, ignore_errors=True)

                logger.info(f"Extracted compressed file contents to {dest_dir}")

            else:
                src_dir = file_path
                root_dir = None
                found_exes = []
                for root, _, files in os.walk(src_dir):
                    for file in files:
                        if file.lower().endswith(".exe"):
                            found_exes.append(file)
                        if file.lower() in [exe.lower() for exe in expected_exes]:
                            root_dir = root
                            logger.debug(f"Found executable: {file} in: {root_dir}")
                            break
                    if root_dir:
                        break
                if not root_dir:
                    raise ValueError(
                        f"No expected executable ({', '.join(expected_exes)}) found in source folder. Found: {', '.join(found_exes) if found_exes else 'none'}"
                    )

                files = []
                for root, _, filenames in os.walk(root_dir):
                    files.extend(os.path.join(root, fname) for fname in filenames)

                # delete counterparts
                dst_list = []
                for src in files:
                    rel_path = os.path.relpath(src, root_dir).replace(os.sep, "/")
                    dst = os.path.join(dest_dir, rel_path)
                    dst_list.append(dst)
                for d in dst_list:
                    self.delete_existing_file(d)

                for i, src in enumerate(files):
                    if self.is_canceled:
                        return
                    rel_path = os.path.relpath(src, root_dir).replace(os.sep, "/")
                    dst = os.path.join(dest_dir, rel_path)

                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    progress = ((i + 1) / len(files)) * 100
                    self.emit_state(
                        InstallState.INSTALLING_FILES, int(progress), rel_path
                    )
                    logger.debug(f"Copied: {rel_path}")

                for root, dirs, _ in os.walk(root_dir):
                    for d in dirs:
                        src_subdir = os.path.join(root, d)
                        rel_subdir = os.path.relpath(src_subdir, root_dir).replace(
                            os.sep, "/"
                        )
                        dst_subdir = os.path.join(dest_dir, rel_subdir)
                        os.makedirs(dst_subdir, exist_ok=True)
                        logger.debug(f"Created directory: {dst_subdir}")

                logger.info(f"Title Update copied to {dest_dir}")

            root_dir_name = os.path.basename(root_dir) if root_dir else ""
            subfolder_path = (
                os.path.join(dest_dir, root_dir_name) if root_dir_name else ""
            )
            if (
                subfolder_path
                and os.path.exists(subfolder_path)
                and os.path.isdir(subfolder_path)
            ):
                logger.debug(
                    f"Found subfolder {root_dir_name} in {dest_dir}, moving contents to root"
                )
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

            if not self.is_canceled:
                if not self.game_mgr.validateAndUpdateGameExeSHA1(
                    self.game_path, config_mgr
                ):
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
            if isinstance(e, PermissionError):
                ErrorHandler.handleError(str(e))
            else:
                ErrorHandler.handleError(
                    f"Failed to install Title Update {self.update_name}: {str(e)}"
                )

            self.error_signal.emit(str(e))
            if not self.is_canceled:
                self.cancel()

    def install_squad_update(self):
        """Install squad/fut update to game settings folder, handling both compressed and non-compressed files."""
        if self.is_canceled:
            return
        try:
            logger.info(f"Installing Squad Update: {self.update_name}")
            state = (
                InstallState.INSTALLING_SQUADS
                if self.tab_key == self.game_mgr.getTabKeySquadsUpdates()
                else InstallState.INSTALLING_FUT_SQUADS
            )
            dst_path = self.game_mgr.getGameSettingsFolderPath(self.game_path)
            main_data_mgr = MainDataManager()
            ext = os.path.splitext(self.file_path)[1].lower()
            is_compressed = ext in main_data_mgr.getCompressedFileExtensions()
            file_path = Path(self.file_path).resolve()

            self.emit_state(state, 0, os.path.basename(self.file_path))
            time.sleep(0.5)

            if is_compressed:
                pwd = main_data_mgr.getKey()
                os.makedirs(dst_path, exist_ok=True)

                seven_z = main_data_mgr.get7z()
                if not os.path.exists(seven_z):
                    raise FileNotFoundError(f"7z tool not found at: {seven_z}")

                extract_cmd = [
                    seven_z,
                    "x",
                    str(file_path),
                    f"-o{dst_path}",
                    "-y",
                    "-bb3",
                    "-bsp1",
                ]
                if pwd:
                    extract_cmd.insert(2, f"-p{pwd}")

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                process = subprocess.Popen(
                    extract_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    startupinfo=startupinfo,
                )

                current_progress = 0
                current_file = ""

                if process.stdout:
                    for line in process.stdout:
                        if self.is_canceled:
                            process.terminate()
                            return

                        output = line.strip()
                        if output.startswith("- ") or output.startswith("Extracting"):
                            filename = (
                                output.replace("- ", "")
                                .replace("Extracting  ", "")
                                .strip()
                            )
                            if filename:
                                current_file = filename.replace("\\", "/")
                                self.emit_state(state, current_progress, current_file)
                        elif "%" in output:
                            match = re.search(r"(\d+)%", output)
                            if match:
                                current_progress = int(match.group(1))
                                self.emit_state(state, current_progress, current_file)

                process.wait()

                logger.info(f"Extracted squad file to {dst_path}")
            else:
                dst_file = os.path.join(dst_path, os.path.basename(self.file_path))
                shutil.copy2(self.file_path, dst_file)
                self.emit_state(state, 100, os.path.basename(self.file_path))
                logger.info(f"Installed squad file: {dst_file}")

        except Exception as e:
            ErrorHandler.handleError(
                f"Failed to install Squad Update {self.update_name}: {str(e)}"
            )
            self.error_signal.emit(str(e))

    def clean_steam_files(self):
        """Delete Steam-related files if the game is not from Steam to avoid compatibility issues."""
        if not self.is_canceled and "steam" not in self.game_path.lower():
            logger.info(
                f"Non-Steam game detected in path: {self.game_path}, cleaning Steam-related files..."
            )
            files_to_delete = [
                os.path.join(self.game_path, "steam_appid.txt"),
                os.path.join(self.game_path, "EAStore.ini"),
            ]
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
                self.game_mgr.getSelectedGameId(self.game_path),
            )
            os.makedirs(backup_dir, exist_ok=True)
            backup_file = os.path.join(
                backup_dir, f"settings{datetime.now().strftime('%Y-%m-%d')}.zip"
            )

            self.install_core.emit_state(
                InstallState.BACKING_UP_SETTINGS, 0, os.path.basename(backup_file)
            )
            time.sleep(0.5)

            if os.path.exists(backup_file):
                logger.info(
                    f"A backup file already exists with today's date, skipping backup: {backup_file}"
                )
                return

            shutil.make_archive(backup_file[:-4], "zip", settings_path)
            self.install_core.emit_state(InstallState.BACKING_UP_SETTINGS, 100, "100%")
            time.sleep(0.5)
            logger.info(f"Settings folder backed up: {backup_file}")
        except Exception as e:
            ErrorHandler.handleError(
                f"Failed to backup game settings folder for {self.game_path}: {str(e)}"
            )
            self.install_core.error_signal.emit(str(e))

    def backup_title_update(self, update_name: str) -> bool:
        """Backup current Title Update to Profiles, excluding specified folders."""
        if self.install_core.is_canceled:
            return False
        try:
            if not self.config_mgr.getConfigKeyBackupTitleUpdate():
                return True
            update = self.game_mgr.getInstalledCurrentTitleUpdate(self.config_mgr)
            installed_update = (
                update.get(self.game_mgr.getTitleUpdateNameKey(), "Unknown Update")
                if update
                else "Unknown Update"
            )
            self.install_core.emit_state(
                InstallState.BACKING_UP_TITLE_UPDATE, 0, installed_update
            )
            time.sleep(0.5)
            logger.info(f"Backing up Title Update: {installed_update}")

            game_id = self.game_mgr.getSelectedGameId(self.game_path)
            base_backup_dir = self.game_mgr.getProfileDirectory(
                game_id, self.game_mgr.getProfileTypeTitleUpdate()
            )
            full_backup_dir = os.path.join(base_backup_dir, installed_update)

            compressed_extensions = MainDataManager().getCompressedFileExtensions()
            conflict_exists = os.path.exists(full_backup_dir) or any(
                os.path.exists(f"{full_backup_dir}{ext}")
                for ext in compressed_extensions
            )

            if conflict_exists:
                display_name = full_backup_dir
                for ext in compressed_extensions:
                    if os.path.exists(f"{full_backup_dir}{ext}"):
                        display_name = f"{full_backup_dir}{ext}"
                        break
                confirmation_message = (
                    f'"Backup current title update" option is enabled.\n\n'
                    f'A folder or compressed file already exists at:\n"{display_name}"\n\n'
                    f"Do you want to replace it?"
                )
                response = NotificationHandler.showConfirmation(confirmation_message)
                if response == "Yes":
                    if os.path.exists(full_backup_dir):
                        shutil.rmtree(full_backup_dir)
                        logger.info(
                            f"Deleted existing backup folder: {full_backup_dir}"
                        )
                    for ext in compressed_extensions:
                        compressed_path = f"{full_backup_dir}{ext}"
                        if os.path.exists(compressed_path):
                            os.remove(compressed_path)
                            logger.info(
                                f"Deleted existing compressed file: {compressed_path}"
                            )
                elif response == "No":
                    logger.info("Backup operation skipped by user")
                    return True
                elif response == "Cancel":
                    logger.info("Backup operation canceled by user")
                    self.install_core.cancel()
                    return False

            os.makedirs(full_backup_dir, exist_ok=True)
            logger.info(f"Created backup directory: {full_backup_dir}")

            files = []
            exclude_folders = ["Data", "FIFAModData"]
            for root, dirs, filenames in os.walk(self.game_path):
                dirs[:] = [
                    d
                    for d in dirs
                    if d.lower() not in [f.lower() for f in exclude_folders]
                    and not d.lower().startswith("original_")
                ]
                files.extend(os.path.join(root, fname) for fname in filenames)

            for i, src in enumerate(files):
                if self.install_core.is_canceled:
                    return False
                rel_path = os.path.relpath(src, self.game_path).replace(os.sep, "/")
                dst = os.path.join(full_backup_dir, rel_path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                progress = ((i + 1) / len(files)) * 100
                self.install_core.emit_state(
                    InstallState.BACKING_UP_TITLE_UPDATE,
                    int(progress),
                    f"{int(progress)}%",
                )

            for root, dirs, _ in os.walk(self.game_path):
                dirs[:] = [
                    d
                    for d in dirs
                    if d.lower() not in [f.lower() for f in exclude_folders]
                    and not d.lower().startswith("original_")
                ]
                for d in dirs:
                    src_subdir = os.path.join(root, d)
                    rel_subdir = os.path.relpath(src_subdir, self.game_path).replace(
                        os.sep, "/"
                    )
                    dst_subdir = os.path.join(full_backup_dir, rel_subdir)
                    os.makedirs(dst_subdir, exist_ok=True)

            logger.info(f"Title Update backed up to {full_backup_dir}")
            return True
        except Exception as e:
            ErrorHandler.handleError(
                f"Failed to backup Title Update {update_name}: {str(e)}"
            )
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
            self.install_core.emit_state(
                InstallState.DELETING_STORED_TITLE_UPDATE, 0, simplified_path
            )
            self._common_delete(path)
            time.sleep(0.5)
        except Exception as e:
            ErrorHandler.handleError(
                f"Failed to delete stored Title Update {path}: {str(e)}"
            )
            self.install_core.error_signal.emit(str(e))

    def delete_squads_after_install(self, path: str):
        """Delete squads files after installation from Profiles."""
        if self.install_core.is_canceled:
            return
        try:
            if not self.config_mgr.getConfigKeyDeleteSquadsAfterInstall():
                return
            simplified_path = f"Profiles/{os.path.basename(path)}"
            self.install_core.emit_state(
                InstallState.DELETING_SQUAD_FILES, 0, simplified_path
            )
            self._common_delete(path)
            time.sleep(0.5)
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
            self.install_core.emit_state(
                InstallState.DELETING_LIVE_TUNING_UPDATE, 0, path
            )
            self._common_delete(path)
            time.sleep(0.5)
        except Exception as e:
            ErrorHandler.handleError(
                f"Failed to delete live tuning update for {game_path}: {str(e)}"
            )
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
