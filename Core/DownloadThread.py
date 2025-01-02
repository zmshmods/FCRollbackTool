from PySide6.QtCore import QThread
import os
import time
import subprocess
import ctypes
import cloudscraper
import certifi
from lxml import html
import sys
import Core.Initializer
from Core.Logger import logger
from urllib.parse import unquote
from PySide6.QtCore import QThread, Signal
import threading
class DownloadThread(QThread):
    paused_signal = Signal()  # إشارة عند الإيقاف
    resumed_signal = Signal()  # إشارة عند الاستئناف
    cancel_status_signal = Signal(str)  # إشارة تحتوي حالة الإلغاء
    download_completed_signal = Signal()  # إشارة عند اكتمال التنزيل
    def __init__(self, url, game_profile, update_name):
        super().__init__()
        self.url = url
        self.game_profile = game_profile
        self.update_name = update_name
        self.temp_folder = Core.Initializer.Initializer.create_temp_folder()
        self.cancel_flag = False
        self.is_paused = False  # حالة الإيقاف
        self.process = None
        self.total = 0.0  

    def run(self):
        self.download_file()

    def cancel(self):
        """إلغاء عملية التنزيل وتنظيف الملفات المؤقتة"""
        self.cancel_flag = True
        self.cancel_status_signal.emit("canceling")  # إرسال حالة "قيد الإلغاء"

        # تشغيل الإلغاء في خيط منفصل
        cancel_thread = threading.Thread(target=self._cancel_process)
        cancel_thread.start()

    def _cancel_process(self):
        """وظيفة تنفيذ الإلغاء في الخلفية"""
        try:
            if self.process and self.process.poll() is None:  # إذا كانت العملية نشطة
                self.process.terminate()  # إنهاء العملية الجارية
                self.process.wait()  # الانتظار حتى تنتهي العملية تمامًا
                logger.info("Download process canceled.")
        except Exception as e:
            logger.error(f"Error during process termination: {str(e)}")

        # تنظيف الملفات المؤقتة بعد الإلغاء
        try:
            Core.Initializer.Initializer.create_temp_folder(clean=True)
            logger.info("Temporary files cleaned successfully.")
        except Exception as e:
            logger.error(f"Failed to clean temporary folder during cancel: {str(e)}")

        # إرسال الإشارة عند اكتمال الإلغاء
        self.cancel_status_signal.emit("canceled")

    def pause(self):
        """إيقاف التنزيل"""
        self.is_paused = True
        self.paused_signal.emit()  # إرسال إشارة الإيقاف

    def resume(self):
        """استئناف التنزيل"""
        self.is_paused = False
        self.resumed_signal.emit()  # إرسال إشارة الاستئناف

    def handle_error(self, message):
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)
        logger.error(message)

    def fetch_direct_download_url(self, xpath_expression='//a[@id="downloadButton"]'):
        try:
            scraper = cloudscraper.create_scraper()
            response = scraper.get(self.url, headers={"User-Agent": "Mozilla/5.0"}, verify=certifi.where())
            response.raise_for_status()
            tree = html.fromstring(response.text)
            direct_link = tree.xpath(xpath_expression)
            if direct_link:
                return direct_link[0].get('href')
            raise Exception("Failed to retrieve the direct download link.")
        except Exception as e:
            self.handle_error(f"Error fetching direct download URL: {str(e)}")
            return None

    def download_file(self):
        try:
            logger.info(f"Starting the download for update: {self.update_name}")
            self.start_time = time.time()
            direct_url = self.fetch_direct_download_url()
            if not direct_url:
                raise Exception("Failed to fetch direct download URL.")
            self.url = direct_url

            filename = self.extract_filename(self.url)
            file_temp_path = os.path.join(self.temp_folder, filename)
            log_file_path = os.path.join(self.temp_folder, f"Download_{self.update_name}.log")

            logger.info(f"Log file path: {log_file_path}")

            command = [
                os.path.join(os.getcwd(), "Data", "ThirdParty", "aria2c.exe"),
                "--max-connection-per-server=8",
                "--split=8",
                "--continue=true",
                "--max-download-limit=0",
                "--retry-wait=5",  # وقت الانتظار بين المحاولات (بالثواني)
                "--max-tries=0",  # محاولات غير محدودة
                "--timeout=60",  # وقت المهلة للاتصال
                "--dir", self.temp_folder,
                "--out", filename,
                "--summary-interval=1",
                "--log-level=debug",
                self.url
            ]

            # إعداد التشغيل الصامت
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                startupinfo=startupinfo  # تشغيل بدون نافذة CMD
            )

            with open(log_file_path, 'a') as log_file:
                for line in iter(self.process.stdout.readline, ''):
                    if self.cancel_flag:
                        self.process.terminate()
                        self.process.wait()
                        logger.info("Download cancelled by user.")
                        return

                    while self.is_paused:
                        time.sleep(0.1)

                    line = line.strip()
                    if line.startswith('[') and '#' in line:
                        sys.stdout.write("\r" + line)
                        sys.stdout.flush()
                        log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {line}\n")
                        log_file.flush()

            for line in self.process.stderr:
                logger.error(f"aria2c Error: {line.strip()}")

            self.process.wait()

            if self.process.returncode == 0:
                if not self.cancel_flag:
                    final_path = self.move_to_profiles(file_temp_path, filename)
                    logger.info(f"Download successful! File moved to: {final_path}")
                    self.download_completed_signal.emit()
                else:
                    logger.info("Download was cancelled")
        except Exception as e:
            self.handle_error(f"Download Error: {str(e)}")

    def extract_filename(self, url):
        try:
            # استخراج اسم الملف من URL
            encoded_filename = os.path.basename(url.split('?')[0])
            # فك ترميز اسم الملف
            decoded_filename = unquote(encoded_filename)
            return decoded_filename
        except Exception as e:
            self.handle_error(f"Error extracting filename: {str(e)}")
            return "unknown_file"

    def move_to_profiles(self, file_temp_path, filename):
        try:
            profiles_folder = os.path.join(os.getcwd(), "Profiles", self.game_profile, "TitleUpdates")
            os.makedirs(profiles_folder, exist_ok=True)
            filename = filename.replace("+", " ")
            final_path = os.path.join(profiles_folder, filename)

            if os.path.exists(final_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(final_path):
                    final_path = os.path.join(profiles_folder, f"{base} ({counter}){ext}")
                    counter += 1
            os.rename(file_temp_path, final_path)
            logger.info(f"File moved to: {final_path}")
            return final_path
        except Exception as e:
            self.handle_error(f"Error moving file: {str(e)}")
            raise e

if __name__ == "__main__":
    example_url = "https://www.mediafire.com/file/9f9jg3r3smhdoqj/OriginSetup.exe/file"
    game_profile = "MyGameProfile"
    update_name = "OriginSetup"

    downloader = DownloadThread(url=example_url, game_profile=game_profile, update_name=update_name)
    downloader.run()