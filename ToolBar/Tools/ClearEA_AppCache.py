import os
import ctypes
import psutil
import shutil
import winreg
import time
from Core.Logger import logger

EACachePaths = [
    os.path.join(os.getenv("USERPROFILE"), "AppData", "Roaming", "EA"),
    os.path.join(os.getenv("USERPROFILE"), "AppData", "Roaming", "Electronic Arts"),
    os.path.join(os.getenv("USERPROFILE"), "AppData", "Local", "EADesktop"),
    os.path.join(os.getenv("USERPROFILE"), "AppData", "Local", "Electronic Arts"),
    os.path.join(os.getenv("USERPROFILE"), "AppData", "Local", "EALaunchHelper")
]

# === الدوال المساعدة ===
def is_eadesktop_running():
    """التحقق إذا كان تطبيق EA Desktop قيد التشغيل"""
    try:
        return next((proc.info['pid'] for proc in psutil.process_iter(['pid', 'name']) if proc.info['name'] == "EADesktop.exe"), None)
    except psutil.Error as e:
        logger.error(f"Error checking if EA Desktop is running: {e}")
        return None

def terminate_eadesktop(pid):
    """إنهاء تطبيق EA Desktop وجميع العمليات التابعة بالقوة إذا كانت قيد التشغيل"""
    try:
        # إنهاء جميع العمليات التابعة EACefSubProcess.exe
        logger.info("Scanning for EACefSubProcess.exe processes.")
        cef_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == "EACefSubProcess.exe":
                    cef_count += 1
                    sub_pid = proc.info['pid']
                    sub_process = psutil.Process(sub_pid)
                    if sub_process.is_running():
                        sub_process.terminate()
                        sub_process.wait(timeout=10)
                        logger.info(f"EACefSubProcess.exe (PID: {sub_pid}) force closed.")
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
                logger.error(f"Failed to process EACefSubProcess.exe with error: {e}")
        if cef_count > 0:
            logger.info(f"Total EACefSubProcess.exe processes found and terminated: {cef_count}")
        else:
            logger.info("No EACefSubProcess.exe processes found running.")

        # إضافة إغلاق EALocalHostSvc.exe
        logger.info("Scanning for EALocalHostSvc.exe processes.")
        svc_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == "EALocalHostSvc.exe":
                    svc_count += 1
                    svc_pid = proc.info['pid']
                    svc_process = psutil.Process(svc_pid)
                    if svc_process.is_running():
                        svc_process.terminate()
                        svc_process.wait(timeout=10)
                        logger.info(f"EALocalHostSvc.exe (PID: {svc_pid}) force closed.")
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
                logger.error(f"Failed to process EALocalHostSvc.exe with error: {e}")
        if svc_count > 0:
            logger.info(f"Total EALocalHostSvc.exe processes found and terminated: {svc_count}")
        else:
            logger.info("No EALocalHostSvc.exe processes found running.")

        # إنهاء العملية الرئيسية EADesktop.exe
        logger.info(f"Attempting to terminate EADesktop.exe with PID: {pid}")
        try:
            process = psutil.Process(pid)
            if process.is_running():
                process.terminate()
                process.wait(timeout=10)
                logger.info(f"EADesktop.exe (PID: {pid}) force closed.")
            else:
                logger.warning(f"EADesktop.exe (PID: {pid}) is not running.")
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
            logger.error(f"Failed to terminate EADesktop.exe with error: {e}")

        # الانتظار لمدة 5 ثوانٍ بعد الإغلاق
        logger.info("Waiting 5 seconds before proceeding with cleanup...")
        time.sleep(5)

        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
        logger.error(f"Failed to force close EA Desktop or its subprocesses: {e}")
        return False

def confirm_action(message, title, icon=0x20 | 0x4):
    """عرض مربع حوار لتأكيد إجراء من المستخدم"""
    return ctypes.windll.user32.MessageBoxW(0, message, title, icon)

def delete_cache_files():
    """حذف ملفات الكاش وإعادة تشغيل EA Desktop"""
    try:
        logger.info("=== Starting EA Desktop Cache Cleanup ===")

        # تأكيد المستخدم لمسح الكاش
        if confirm_action(
            "Clearing the cache may help resolve common issues.\nYou will need to re-login after clearing the cache.\n\n Do you want to continue?",
            "Clear EA Cache") != 6:
            logger.info("User canceled cache cleanup.")
            return

        pid = is_eadesktop_running()
        if pid:
            logger.info(f"EA Desktop is running (PID: {pid}). Requesting user confirmation to close it.")
            if confirm_action(f"EA Desktop is running (PID: {pid}).\nForce close to continue?", "Clear EA Cache") != 6:
                logger.info("User declined to close EA Desktop. Aborting cleanup.")
                return

            if not terminate_eadesktop(pid):
                logger.error("Failed to close EA Desktop. Aborting cleanup.")
                return

        # حذف ملفات الكاش
        logger.info("Deleting cache files...")
        deleted_files, total_files = 0, len(EACachePaths)
        for path in EACachePaths:
            if os.path.exists(path):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                        logger.info(f"Deleted directory: {path}")
                    else:
                        os.remove(path)
                        logger.info(f"Deleted file: {path}")
                    deleted_files += 1
                except Exception as e:
                    logger.error(f"Error deleting {path}: {e}")
            else:
                logger.warning(f"Path not found: {path}")

        logger.info(f"Cache cleanup complete. Deleted {deleted_files}/{total_files} files.")

        # إعادة تشغيل التطبيق
        logger.info("Restarting EA Desktop...")
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Electronic Arts\\EA Desktop")
            app_path, _ = winreg.QueryValueEx(reg_key, "DesktopAppPath")
            winreg.CloseKey(reg_key)

            if app_path:
                os.startfile(app_path)
                logger.info(f"EA Desktop restarted from: {app_path}")
            else:
                logger.error("EA Desktop path not found in registry.")
        except Exception as e:
            logger.error(f"Failed to restart EA Desktop: {e}")

    except Exception as e:
        logger.error(f"Unexpected error during cache cleanup: {e}")
        ctypes.windll.user32.MessageBoxW(0, f"Error: {e}", "Error", 0x10)

if __name__ == "__main__":
    delete_cache_files()
