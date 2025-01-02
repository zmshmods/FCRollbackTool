import os
import shutil
import ctypes
import threading
from PySide6.QtCore import Signal, QObject
import subprocess
import psutil
import time
import rarfile
from Core.Logger import logger
import Core.Initializer

# Constants
UPDATE_PROGRESS, UPDATE_MESSAGE, UPDATE_FILE_NAME, UPDATE_LOG = Signal(int), Signal(str), Signal(str), Signal(str)
PROFILES_DIR = os.path.join(os.getcwd(), "Profiles")
SEVEN_ZIP_PATH = os.path.join(os.getcwd(), "Data", "ThirdParty", "7-Zip", "7z.exe")
UNRAR_PATH = os.path.join(os.getcwd(), "Data", "ThirdParty", "UnRAR.exe")

class InstallThread(QObject, threading.Thread):
    update_progress, update_message, update_file_name, update_log = UPDATE_PROGRESS, UPDATE_MESSAGE, UPDATE_FILE_NAME, UPDATE_LOG

    def __init__(self, selected_game_path, update_name, parent=None):
        QObject.__init__(self)
        threading.Thread.__init__(self)
        self.selected_game_path = selected_game_path
        self.update_name = update_name
        self.parent = parent
        self.daemon = True
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()
        
    def handle_error(self, message):
        logger.error(message)
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)
        
    def get_short_game_name(self, path):
        return os.path.basename(path.strip("\\/")).replace("EA SPORTS ", "").replace(" ", "")

    @staticmethod
    def get_running_processes(target_processes=None):
        if target_processes is None:
            target_processes = ["FIFA Editor Tool.exe", "FIFA Mod Manager.exe", "FMT.exe"]
        return [
            (proc.info['name'], proc.info['pid']) 
            for proc in psutil.process_iter(['pid', 'name']) 
            if proc.info['name'] in target_processes
        ]

    def run(self):
        if self.stop_event.is_set():
            return

        short_game_name = self.get_short_game_name(self.selected_game_path)
        install_source = self.find_install_source(short_game_name)
        installed_update = self.get_installed_update_name()

        if installed_update:
            self.backup_files_if_enabled(short_game_name, installed_update, install_source)
            
            # تخطي التنظيف إذا تم تفعيل خيار الباك أب
            config = Core.Initializer.Initializer.initialize_and_load_config()
            if config.get("install_options", {}).get("backup_checkbox", False):
                logger.info("Skipping cleaning as backup option is enabled.")
            else:
                self.clean_game_directory(install_source)

        self.general_install_update(short_game_name)
        self.delete_stored_update(short_game_name, self.update_name)

        if self.parent and hasattr(self.parent, 'table_component'):
            Core.Initializer.Initializer.validate_and_update_crc(self.selected_game_path, self.parent.table_component)
            self.parent.table_component.update_table(self.selected_game_path)

        self.update_progress.emit(100)
        self.update_message.emit("<span style='color:white'>Installation completed successfully.</span>")
        logger.info("Installation completed successfully.")


    def find_install_source(self, game_name):
        source = os.path.join(PROFILES_DIR, game_name, "TitleUpdates", self.update_name)
        for ext in (".rar", ".zip", ".7z"):
            if os.path.isfile(source + ext):
                return source + ext
        if not os.path.exists(source):
            raise FileNotFoundError(f"Install source not found: {source}")
        return source

    def get_source_contents(self, source):
        if os.path.isdir(source):
            return [i for i in os.listdir(source) if os.path.isfile(os.path.join(source, i))], \
                [i for i in os.listdir(source) if os.path.isdir(os.path.join(source, i))]
        elif source.endswith((".rar", ".zip", ".7z")):
            return self.list_archive_contents(source)
        else:
            logger.warning(f"Unsupported install source: {source}")
            return [], []

    def list_archive_contents(self, source):
        files, dirs = [], []
        if source.endswith(".rar"):
            with rarfile.RarFile(source) as archive:
                for member in archive.infolist():
                    item = member.filename.split('/')[0]
                    (dirs if member.isdir() else files).append(item)
        else:
            result = subprocess.run([SEVEN_ZIP_PATH, "l", source], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"7z failed to list contents of {source}")
            for line in result.stdout.splitlines():
                parts = line.split()
                if parts and parts[-1] != source:
                    item = parts[-1].split('/')[0]
                    (dirs if item.endswith('/') else files).append(item.strip('/'))
        return files, dirs

    def clean_game_directory(self, source):
        self.update_message.emit("<span style='color:white;'>Current Task:</span> <span style='color:#00ff00;'>Cleaning old TU</span><br>")
        
        files, dirs = self.get_source_contents(source)
        cleaned, not_found, error = [], [], []

        # تحديد المجلدات أو الملفات المفقودة فقط كـ "Not Found"
        missing_items = set()
        for item in dirs + files:
            path = os.path.join(self.selected_game_path, item)
            if not os.path.exists(path):
                # إضافة المجلد الرئيسي فقط عند عدم العثور على أي عنصر فرعي
                missing_items.add(os.path.dirname(path) if os.path.isfile(path) else path)

        not_found.extend(missing_items)  # تسجيل المجلدات والملفات غير الموجودة
        
        # تنظيف الملفات والمجلدات الموجودة فقط
        for item in dirs + files:
            path = os.path.join(self.selected_game_path, item)
            if os.path.exists(path):  # تنظيف فقط إذا كان موجودًا
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    cleaned.append(path)  # إضافة إلى قائمة الملفات المحذوفة بنجاح
                except Exception as e:
                    if "[WinError 2]" not in str(e):  # تجاهل الأخطاء المتعلقة بـ "Not Found"
                        error.append(f"{path} - {e}")  # تسجيل الأخطاء الحقيقية فقط

        # تسجيل التفاصيل
        self.log_cleaning_details(cleaned, not_found, error)



    def general_install_update(self, game_name):
        path = self.find_install_source(game_name)
        if os.path.isdir(path):
            self.update_message.emit(f"<span style='color:white;'>Current Task:</span> <span style='color:#00ff00;'>Installing from folder</span><br />{self.update_name}")
            self.InstallFromFolder(path, self.selected_game_path)
        elif path.endswith((".rar", ".zip", ".7z")):
            self.extract_update(path)
        else:
            raise FileNotFoundError(f"Update file or directory {self.update_name} not found.")

    def InstallFromFolder(self, src, dest):
        total_items = sum([len(files) + len(dirs) for _, dirs, files in os.walk(src)])
        installed_items = 0

        def install_recursive(src, dest, root):
            nonlocal installed_items
            for item in os.listdir(src):
                s, d = os.path.join(src, item), os.path.join(dest, item)
                try:
                    if os.path.isdir(s):
                        os.makedirs(d, exist_ok=True)
                        self.update_message.emit(f"<span style='color:white'>Current Task:</span> <span style='color:#00ff00;'>Installing from back-up folder:</span><br /><span style='color:white'>{os.path.basename(src)}</span>")
                        install_recursive(s, d, root)
                    else:
                        shutil.copy2(s, d)
                        self.update_message.emit(f"<span style='color:white'>Current Task:</span> <span style='color:#00ff00;'>Installing from back-up folder:</span><br /><span style='color:white'><b>{os.path.basename(os.path.dirname(s))}</b>/{os.path.basename(s)}</span>")
                    installed_items += 1
                    self.update_progress.emit(int((installed_items / total_items) * 100))
                except Exception as e:
                    logger.error(f"Error installing {s}: {e}")

        install_recursive(src, dest, src)

    def extract_update(self, file_path):
        self.update_message.emit(f"<span style='color:white'>Current Task:</span> <span style='color:#00ff00;'>Extracting</span>")
        logger.info(f"Starting extraction of {file_path}")

        try:
            if file_path.endswith(".rar"):
                rarfile.UNRAR_TOOL = UNRAR_PATH
                with rarfile.RarFile(file_path) as rf:
                    total_files = len(rf.infolist())
                    for i, member in enumerate(rf.infolist()):
                        if self.stop_event.is_set():
                            logger.info("Installation stopped by user.")
                            return
                        rf.extract(member, self.selected_game_path)
                        self.update_ui(member.filename, i, total_files)
            elif file_path.endswith((".7z", ".zip")):
                cmd = [SEVEN_ZIP_PATH, "x", file_path, f"-o{self.selected_game_path}", "-y"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"Extraction failed for {file_path}: {result.stderr}")
                self.process_7z_output(result.stdout)
            else:
                raise ValueError(f"Unsupported file extension for {file_path}")
        except rarfile.Error as e:
            self.handle_error(f"Rarfile extraction error: {str(e)}")
        except Exception as e:
            self.handle_error(f"Error during extraction: {str(e)}")

    def update_ui(self, path, index, total):
        parts = path.split("/")
        folder_name, file_name = (parts[0], parts[-1]) if len(parts) > 1 else ("", parts[0])
        full_name = f"<b>{folder_name}</b>/{file_name}" if folder_name else file_name
        self.update_file_name.emit(full_name)
        self.update_message.emit(f"<span style='color:white'>Current Task:</span> <span style='color:#00ff00;'>Extracting</span><br /><span style='color:white'>{full_name}</span>")
        self.update_progress.emit(int((index + 1) / total * 100))

    def process_7z_output(self, output):
        for line in output.splitlines():
            if "Extracting" in line:
                path = line.split()[-1]
                self.update_ui(path, 0, 1)
                logger.info(f"Extracted: {path}")
#--------------------------------------------- خيارات التثبيت ----------------------------------------------------------
    def get_installed_update_name(self):
        for row in range(self.parent.table_component.table.rowCount()):
            status = self.parent.table_component.table.item(row, 3)
            if status and status.text() == "Installed (Current)":
                return self.parent.table_component.table.item(row, 0).text() if self.parent.table_component.table.item(row, 0) else None
        return None
    
    def backup_files_if_enabled(self, game_name, installed_update, source):
        if not Core.Initializer.Initializer.initialize_and_load_config().get("install_options", {}).get("backup_checkbox", False):
            return
        backup_dir = os.path.join(PROFILES_DIR, game_name, "TitleUpdates", installed_update)
        os.makedirs(backup_dir, exist_ok=True)
        self.update_message.emit(f"<span style='color:white'>Current Task:</span> <span style='color:yellow;'>Backing-Up</span><br />Your current TU: {installed_update}")
        
        for item in set(self.get_source_contents(source)[0] + self.get_source_contents(source)[1]):
            source_path, backup_path = os.path.join(self.selected_game_path, item), os.path.join(backup_dir, item)
            if not os.path.exists(source_path):
                logger.warning(f"Source not found: {source_path}. Skipping.")
                continue
            try:
                # إذا كان العنصر موجودًا في الوجهة، قم بحذفه
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path) if os.path.isdir(backup_path) else os.remove(backup_path)
                # نقل العنصر
                shutil.move(source_path, backup_path)
                self.update_message.emit(f"<span style='color:white'>Current Task:</span> <span style='color:yellow;'>Moving {'Directory' if os.path.isdir(source_path) else 'File'}</span><br />{item}")
            except Exception as e:
                logger.error(f"Failed to move {item}: {e}")

    def delete_stored_update(self, game_name, update_name):
        config = Core.Initializer.Initializer.initialize_and_load_config()
        if config.get("install_options", {}).get("delete_stored_update_checkbox", False):
            profiles_path = os.path.join(PROFILES_DIR, game_name, "TitleUpdates")
            for path in [f"{profiles_path}/{update_name}{ext}" for ext in (".rar", ".zip", ".7z")] + [os.path.join(profiles_path, update_name)]:
                if os.path.exists(path):
                    (os.remove if os.path.isfile(path) else shutil.rmtree)(path)
                    logger.info(f"Deleted stored update {update_name} from {profiles_path}")

    def log_cleaning_details(self, cleaned, not_found, error):
        log_file = os.path.join(os.getcwd(), "logs", "Installation_Cleaning_Details.txt")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        old_logs = ""
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as log:
                old_logs = log.read()
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"- Cleaning Summary {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            log.write(f"Cleaned: {len(cleaned)}, Not Found: {len(not_found)}, Errors: {len(error)}\n\n")  # سطر فارغ بعد الملخص
            log.write("- Errors:\n" + ("\n".join(error) if error else "No errors.") + "\n\n")  # سطر فارغ بعد الأخطاء
            log.write("- Not Found:\n" + ("\n".join(not_found) if not_found else "No missing files or directories.") + "\n\n")  # سطر فارغ بعد غير الموجودة
            log.write("- Cleaned:\n" + ("\n".join(cleaned) if cleaned else "No files or directories were cleaned.") + "\n")
            log.write("=" * 50 + "\n" + old_logs)
        logger.info(f"Summary: Cleaned: {len(cleaned)}, Not Found: {len(not_found)}, Errors: {len(error)}, For more details, check Installation_Cleaning_Details.txt in Logs folder")
