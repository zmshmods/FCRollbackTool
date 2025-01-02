
import json
import os
import ctypes
import psutil
import subprocess
import time
import glob
import shutil
import winreg
import atexit
import signal
import sys
import threading
from Core.Logger import logger
def safe_restore_configs(): #استعادة ملفات النسخ الاحتياطي إلى الأسماء الأصلية عند الإغلاق.
    try:
        if backup_files:
            logger.info("Restoring backup files before exit...")
            handle_configs("", action="restore")
    except Exception as e:
        logger.error(f"Error in safe_restore_configs: {e}")
# تسجيل دالة الاستعادة مع `atexit` لضمان التنفيذ عند الإغلاق
atexit.register(safe_restore_configs)
def signal_handler(sig, frame):
    safe_restore_configs()
    sys.exit(0)
# تسجيل معالج الإشارات للإشارات SIGINT و SIGTERM
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
# تعريف الثوابت
CONFIG_FILE_PATH = "config.json"
FC25 = "EA SPORTS FC 25"
FC24 = "EA SPORTS FC 24"
LiveEditorLauncher = "Launcher.exe"
LiveEditorDLL = "FCLiveEditor.DLL"
backup_files = []  # قائمة النسخ الاحتياطية
stop_event = threading.Event()
def handle_error(message, log=True):
    """معالجة الأخطاء وإظهار رسالة عبر ctypes."""
    if log:
        logger.error(message)
    ctypes.windll.user32.MessageBoxW(0, message, "Error Launch Vanilla", 0x10)

def is_game_running(game_exe):
    """التحقق مما إذا كانت اللعبة تعمل بالفعل."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and os.path.basename(game_exe).lower() in proc.info['name'].lower():
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

def terminate_launcher_process():
    """إيقاف عملية Launcher.exe إذا كان في نفس المسار ملف FCLiveEditor.DLL."""
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            if LiveEditorLauncher in proc.name():
                process_path = proc.exe()
                fclive_editor_dll_path = os.path.join(os.path.dirname(process_path), LiveEditorDLL)
                if os.path.exists(fclive_editor_dll_path):
                    proc.terminate()
                    logger.info(f"Found and terminated process: {proc.name()} with PID {proc.pid} because {LiveEditorDLL} was found.")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            handle_error(f"Error in terminating process: {e}")

def wait_ea_processes(game_exe_name, cheat_service_name="EAAntiCheat.GameServiceLauncher.exe"):
    """
    انتظار عملية EAAntiCheat أولاً، ثم مراقبة اللعبة بعد ذلك.
    """
    logger.info(f"Waiting for {cheat_service_name} and {game_exe_name}...")

    # انتظار بدء EAAntiCheat.GameServiceLauncher.exe
    start_time = time.time()
    while time.time() - start_time < 60:
        cheat_running = False
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and cheat_service_name.lower() in proc.info['name'].lower():
                cheat_running = True
                logger.info(f"{cheat_service_name} has started.")
                break
        if cheat_running:
            break
        time.sleep(1)
    else:
        logger.error(f"{cheat_service_name} did not start.")
        return False

    # انتظار إغلاق EAAntiCheat.GameServiceLauncher.exe
    logger.info(f"Waiting for {cheat_service_name} to exit...")
    while True:
        cheat_running = False
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and cheat_service_name.lower() in proc.info['name'].lower():
                cheat_running = True
                break
        if not cheat_running:
            logger.info(f"{cheat_service_name} has exited.")
            break
        time.sleep(1)

    # تحقق من وجود العملية الخاصة باللعبة
    logger.info(f"Checking if {game_exe_name} is running...")
    start_time = time.time()
    game_process = None
    while time.time() - start_time < 3:  # انتظار 3 ثوانٍ
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and game_exe_name.lower() in proc.info['name'].lower():
                game_process = proc
                logger.info(f"Game process {game_exe_name} found with PID {proc.pid}.")
                break
        if game_process:
            break
        time.sleep(1)

    if not game_process:
        logger.error(f"Game process {game_exe_name} did not start after {cheat_service_name} exited.")
        return False

    # مراقبة العملية لمدة 3 ثوانٍ
    logger.info(f"Watching {game_exe_name} stability...")
    start_time = time.time()
    while time.time() - start_time < 3:
        if not game_process.is_running(): 
            logger.error(f"Game process {game_process.pid} has exited prematurely.")
            return False
        time.sleep(1)
    return True

restored_paths = []  # قائمة لتعقب المسارات التي تمت استعادتها
def handle_configs(selected_game_path, action="backup"):
    global backup_files, restored_paths
    try:
        if action == "backup":
            # التعامل مع Steam
            if "steam" in selected_game_path.lower():
                platform = "Steam"
                steam_path = get_steam_path_from_registry()
                if not steam_path:
                    raise Exception("Steam path could not be determined from the registry.")

                userdata_path = os.path.join(steam_path, "userdata")
                userdata_b_path = userdata_path + "_b"

                if os.path.exists(userdata_b_path):
                    shutil.rmtree(userdata_b_path)
                    logger.info(f"[{platform}] Old userdata_b removed.")

                if os.path.exists(userdata_path):
                    os.rename(userdata_path, userdata_b_path)
                    logger.info(f"[{platform}] userdata renamed to userdata_b.")
                    backup_files.append((userdata_path, userdata_b_path))

            # التعامل مع EA Desktop
            else:
                platform = "EA Desktop"
                ea_config_path = os.path.expanduser(r"~\AppData\Local\Electronic Arts\EA Desktop")
                ini_files = glob.glob(os.path.join(ea_config_path, "user_*.ini"))

                for ini_file in ini_files:
                    backup_file = ini_file.replace(".ini", "_b.ini")
                    if os.path.exists(backup_file):
                        os.remove(backup_file)
                        logger.info(f"[{platform}] Old backup {os.path.basename(backup_file)} removed.")
                    if os.path.exists(ini_file):
                        os.rename(ini_file, backup_file)
                        logger.info(f"[{platform}] config {os.path.basename(ini_file)} renamed to {os.path.basename(backup_file)}.")
                        backup_files.append((ini_file, backup_file))

                # التعامل مع Epic Games Launcher
                platform = "Epic Games Launcher"
                epic_config_path = os.path.expanduser(r"~\AppData\Local\EpicGamesLauncher\Saved\Config\Windows")
                game_user_settings = os.path.join(epic_config_path, "GameUserSettings.ini")
                game_user_backup = game_user_settings.replace(".ini", "_b.ini")

                if os.path.exists(game_user_backup):
                    os.remove(game_user_backup)
                    logger.info(f"[{platform}] Old backup {os.path.basename(game_user_backup)} removed.")
                if os.path.exists(game_user_settings):
                    os.rename(game_user_settings, game_user_backup)
                    logger.info(f"[{platform}] config {os.path.basename(game_user_settings)} renamed to {os.path.basename(game_user_backup)}.")
                    backup_files.append((game_user_settings, game_user_backup))

        elif action == "restore":
            for original_path, backup_path in backup_files:
                try:
                    # حذف الملفات/المجلدات إذا لم تكن ضمن المسارات المستعادة
                    if os.path.exists(original_path) and original_path not in restored_paths:
                        if os.path.isdir(original_path):
                            shutil.rmtree(original_path)
                            logger.info(f"[General] Removed {os.path.basename(original_path)} that was auto-created at runtime.")
                        else:
                            os.remove(original_path)
                            logger.info(f"[General] Removed {os.path.basename(original_path)} that was auto-created at runtime.")
                    # استعادة النسخ الاحتياطية
                    if os.path.exists(backup_path):
                        os.rename(backup_path, original_path)
                        logger.info(f"[General] Restored backup: {os.path.basename(backup_path)} to {os.path.basename(original_path)}")
                        restored_paths.append(original_path)  # تعقب المسار المستعاد
                except Exception as e:
                    logger.error(f"[General] Error in restoring {os.path.basename(backup_path)} to {os.path.basename(original_path)}: {e}")

    except Exception as e:
        handle_error(f"Error in handle_configs: {str(e)}", log=True)

def get_steam_path_from_registry():
    """استخراج مسار Steam من الريجستري."""
    try:
        registry_key = r"Software\Valve\Steam"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_key) as key:
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            return steam_path
    except FileNotFoundError:
        handle_error("Steam registry entry not found.")
        return None
    except Exception as e:
        handle_error(f"Error accessing Steam registry: {str(e)}")
        return None

def launch_vanilla_threaded():
    """
    تشغيل وظيفة launch_vanilla في خيط منفصل مع دعم الإيقاف الآمن.
    """
    def task():
        global stop_event
        try:
            with open(CONFIG_FILE_PATH, 'r') as f:
                config = json.load(f)

            selected_game_path = config["selected_game"]
            logger.info(f"Selected game path: {selected_game_path}")

            terminate_launcher_process()

            if FC25 in selected_game_path:
                game_exe = os.path.join(selected_game_path, "FC25.exe")
            elif FC24 in selected_game_path:
                game_exe = os.path.join(selected_game_path, "FC24.exe")
            else:
                raise Exception("Selected game not recognized.")

            # تحقق إذا كانت اللعبة تعمل بالفعل
            running_proc = is_game_running(game_exe)
            if running_proc:
                result = ctypes.windll.user32.MessageBoxW(
                    0,
                    f"{os.path.basename(game_exe)} is already running.\nDo you want to Re-Launch it in vanilla mode?",
                    f"Launch Vanilla for {os.path.basename(game_exe)}",
                    0x24  # MB_YESNO | MB_ICONQUESTION
                )
                if result == 7:  # No
                    return
                elif result == 6:  # Yes
                    logger.info(f"Terminating running game: {os.path.basename(game_exe)}")
                    try:
                        running_proc.terminate()
                        time.sleep(5)
                    except psutil.NoSuchProcess:
                        # إذا كانت العملية غير موجودة، تجاهل الخطأ وأعد تشغيل اللعبة
                        logger.warning("Game process was already terminated. Continuing to launch.")

            # تحقق من وجود الملفات وتغيير الأسماء إذا لزم الأمر
            # للتأكد أن اللايف إديتور لا يستخدم الفيك أنتي شيت
            cheat_service_path = os.path.join(selected_game_path, "EAAntiCheat.GameServiceLauncher.exe")
            cheat_service_backup_path = cheat_service_path + ".backup"
            cheat_dll_path = os.path.join(selected_game_path, "EAAntiCheat.GameServiceLauncher.dll")
            cheat_dll_backup_path = cheat_dll_path + ".backup"

            try:
                if os.path.exists(cheat_service_path) and os.path.exists(cheat_service_backup_path):
                    os.remove(cheat_service_path)
                    os.rename(cheat_service_backup_path, cheat_service_path)
                    logger.info("Replaced FakeEAACLauncher (EAAntiCheat.GameServiceLauncher.exe) with original one.")

                if os.path.exists(cheat_dll_backup_path):
                    if os.path.exists(cheat_dll_path):
                        os.remove(cheat_dll_path)
                    os.rename(cheat_dll_backup_path, cheat_dll_path)
            except Exception as e:
                logger.error(f"Error handling EAAntiCheat files: {e}")

            # تحقق من وجود مجلدات وتغيير الأسماء إذا لزم الأمر
            # MM/FET للتأكد أن لا يفعلون أي مودات على اللعبة
            data_folder = os.path.join(selected_game_path, "Data")
            patch_folder = os.path.join(selected_game_path, "Patch")
            original_data_folder = os.path.join(selected_game_path, "original_Data")
            original_patch_folder = os.path.join(selected_game_path, "original_Patch")

            if os.path.exists(data_folder) and os.path.exists(patch_folder) and os.path.exists(original_data_folder) and os.path.exists(original_patch_folder):
                try:
                    shutil.rmtree(data_folder)
                    shutil.rmtree(patch_folder)
                    os.rename(original_data_folder, data_folder)
                    os.rename(original_patch_folder, patch_folder)
                    logger.info("Replaced Data and Patch folders with their original backups.")
                except Exception as e:
                    logger.error(f"Error handling Data and Patch folders: {e}")

            # نسخ احتياطي للملفات
            handle_configs(selected_game_path, action="backup")

            if os.path.exists(game_exe):
                logger.info(f"Launching game: {game_exe}")
                subprocess.Popen([game_exe], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                # انتظار استقرار اللعبة
                if not wait_ea_processes(os.path.basename(game_exe)):
                    raise Exception("Game process did not stabilize.")

                logger.info("Game launched successfully.")

        except Exception as e:
            handle_error(f"Error occurred: {str(e)}", log=True)
        finally:
            handle_configs(selected_game_path, action="restore")
            stop_event.set()  # وضع علامة انتهاء المهمة

    # تشغيل المهمة في خيط
    threading.Thread(target=task, daemon=True).start()

def stop_thread():
    """
    إيقاف الخيط بأمان.
    """
    stop_event.set()
    logger.info("Thread stop requested.")