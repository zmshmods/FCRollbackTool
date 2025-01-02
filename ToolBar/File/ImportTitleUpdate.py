import os
import sys
import shutil
import ctypes
import requests
import subprocess
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QFileDialog
from Core.Logger import logger
from Core.Initializer import Initializer

class TitleUpdateWorker(QThread):
    update_detected = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, input_path):
        super().__init__()
        self.input_path = input_path
        self._is_running = True

    def run(self):
        try:
            TitleUpdate.process_input(self.input_path)
        finally:
            self._is_running = False

    def quit(self):
        self._is_running = False
        super().quit()
        self.wait()

    def is_running(self):
        return self._is_running


class TitleUpdate:
    @staticmethod
    def select_compressed_file():
        try:
            file, _ = QFileDialog.getOpenFileName(None, "Import Title Update from Compressed File", "", "Compressed Files (*.rar *.zip *.7z)")
            if file:
                worker = TitleUpdateWorker(file)
                worker.update_detected.connect(TitleUpdate.on_update_detected)
                worker.error_occurred.connect(TitleUpdate.on_error_occurred)
                worker.finished.connect(lambda: worker.wait())
                worker.start()
                return worker
        except Exception as e:
            TitleUpdate.show_generic_error(f"Error in select_compressed_file: {e}")
        return None

    @staticmethod
    def select_folder():
        try:
            folder = QFileDialog.getExistingDirectory(None, "Import Title Update from Folder")
            if folder:
                worker = TitleUpdateWorker(folder)
                worker.update_detected.connect(TitleUpdate.on_update_detected)
                worker.error_occurred.connect(TitleUpdate.on_error_occurred)
                worker.finished.connect(lambda: worker.wait())
                worker.start()
                return worker
        except Exception as e:
            TitleUpdate.show_generic_error(f"Error in select_folder: {e}")
        return None

    @staticmethod
    def process_input(input_path):
        try:
            if os.path.isdir(input_path):
                TitleUpdate.process_directory(input_path)
            elif os.path.isfile(input_path):
                TitleUpdate.process_file(input_path)
            else:
                TitleUpdate.handle_error(input_path, "Invalid path. Please provide a valid file or directory.")
        except Exception as e:
            TitleUpdate.show_generic_error(f"Error in process_input: {e}")

    @staticmethod
    def process_directory(input_path):
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.lower() in ("fc25.exe", "fc24.exe"):
                    exe_path = os.path.join(root, file)
                    game_name = "FC25" if "fc25.exe" in file.lower() else "FC24"
                    crc_value = Initializer.calculate_crc(exe_path)
                    TitleUpdate.VerifyTitleUpdate(crc_value, game_name, input_path)
                    return
        TitleUpdate.handle_error(input_path, "Does not contain any EXE. It must contain the game's executable file.")

    @staticmethod
    def process_file(input_path):
        ext = os.path.splitext(input_path)[1].lower()
        if ext in (".zip", ".rar", ".7z"):
            extracted_folder = TitleUpdate.extract_with_7z(input_path)
            if extracted_folder:
                exe_path = TitleUpdate.find_exe(extracted_folder)
                if exe_path:
                    game_name = "FC25" if "FC25.exe" in exe_path else "FC24"
                    crc_value = Initializer.calculate_crc(exe_path)
                    TitleUpdate.VerifyTitleUpdate(crc_value, game_name, input_path)
                    os.remove(exe_path)
                else:
                    TitleUpdate.handle_error(input_path, "Does not contain any EXE. It must contain the game's executable file.")
        else:
            TitleUpdate.handle_error(input_path, "Unsupported file type. Only .zip, .rar, and .7z are supported.")

    @staticmethod
    def find_exe(folder):
        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower() in ("fc25.exe", "fc24.exe"):
                    return os.path.join(root, file)
        return None

    @staticmethod
    def extract_with_7z(archive_path):
        try:
            temp_folder = os.path.join(os.getenv("LOCALAPPDATA"), "fc_rollback_tool", "temp")
            os.makedirs(temp_folder, exist_ok=True)
            command = [
                os.path.join(os.getcwd(), "ThirdParty", "7-Zip", "7z.exe"),
                "x", archive_path, f"-o{temp_folder}", "-y", "-r", "FC25.exe", "FC24.exe"
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                return temp_folder
            logger.error(f"7z Error Output: {result.stderr}")
            TitleUpdate.handle_error(archive_path, f"Error extracting file: {result.stderr}")
            return None
        except Exception as e:
            TitleUpdate.show_generic_error(f"Error extracting archive: {e}")
            return None

    @staticmethod
    def VerifyTitleUpdate(crc_value, game_name, source_path):
        try:
            response = requests.get(f"https://raw.githubusercontent.com/zmshmods/FCRollbackToolUpdates/main/TitleUpdateProfiles/{game_name.lower()}.json", timeout=5)
            response.raise_for_status()
            updates = response.json().get(f"{game_name.lower()}tu-updates", [])
            matched_update = next((update for update in updates if update["crc"] == crc_value), None)

            if matched_update:
                logger.info(f"Detected Title Update: {matched_update['name']}")
                TitleUpdate.SaveFileToProfile(source_path, game_name, matched_update["name"])
            else:
                TitleUpdate.handle_error(source_path, "The Title Update you are trying to import seems to be unrecognized or corrupted")
        except Exception as e:
            TitleUpdate.show_generic_error(f"Error verifying update: {e}")

    @staticmethod
    def SaveFileToProfile(source_path, game_name, update_name):
        try:
            profiles_directory = os.path.join(os.getcwd(), "Profiles", game_name, "TitleUpdates")
            os.makedirs(profiles_directory, exist_ok=True)
            original_extension = os.path.splitext(source_path)[1]
            destination_path = os.path.join(profiles_directory, update_name + original_extension)

            if os.path.isdir(source_path):
                shutil.copytree(source_path, os.path.join(profiles_directory, update_name), dirs_exist_ok=True)
            else:
                shutil.copy2(source_path, destination_path)

            logger.info(f"File Imported Successfully: {update_name} at {destination_path}")
        except Exception as e:
            TitleUpdate.show_generic_error(f"Error saving update: {e}")

    @staticmethod
    def handle_error(file_path, message):
        folder_name = os.path.basename(file_path)
        error_msg = f"Error while trying Import: {folder_name}\n\n{message}"
        logger.error(error_msg)
        ctypes.windll.user32.MessageBoxW(0, error_msg, "Importing error", 0x10)

    @staticmethod
    def show_generic_error(message):
        logger.error(message)
        ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)

    @staticmethod
    def on_update_detected(message):
        logger.info(f"Detected Update: {message}")
        TitleUpdate.update_detected.emit(message)  # Note: This assumes update_detected is a class Signal

    @staticmethod
    def on_error_occurred(message):
        logger.error(f"Error: {message}")
        TitleUpdate.error_occurred.emit(message)  # Note: This assumes error_occurred is a class Signal


if __name__ == "__main__":
    app = QApplication(sys.argv)
    worker = TitleUpdate.select_compressed_file()
    if worker:
        app.exec()