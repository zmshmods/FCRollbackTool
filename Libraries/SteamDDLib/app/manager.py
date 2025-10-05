# SteamDDLib/app/manager.py

import os
import shutil
import requests
import zipfile
import logging
import platform
from pathlib import Path
from .exceptions import DependencyInstallationError

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

class DependencyManager:
    """Manages the automatic installation and updates of DepotDownloader."""
    
    def __init__(self):
        self.base_dir = Path.home() / '.steamddlib'
        self.bin_dir = self.base_dir / 'bin'
        self.version_file = self.base_dir / 'version.txt'
        
        os_name = self._get_os_name()
        architecture = self._get_architecture()
        self.platform_identifier = f"{os_name}-{architecture}"
        
        self.executable_name = "DepotDownloader.exe" if os_name == "windows" else "DepotDownloader"
        self.executable_path = self.bin_dir / self.executable_name
        os.makedirs(self.bin_dir, exist_ok=True)

    def _get_os_name(self) -> str:
        """Normalizes the OS name to match GitHub release asset names."""
        system = platform.system()
        if system == "Windows": return "windows"
        if system == "Linux": return "linux"
        if system == "Darwin": return "macos"
        raise DependencyInstallationError(f"Unsupported operating system: {system}")

    def _get_architecture(self) -> str:
        """Normalizes the CPU architecture to match GitHub release asset names."""
        machine = platform.machine().lower()
        if machine in ["amd64", "x86_64"]: return "x64"
        if machine in ["arm64", "aarch64"]: return "arm64"
        raise DependencyInstallationError(f"Unsupported architecture: {machine}")

    def _get_latest_version(self) -> tuple[str, str]:
        """Fetches the latest release version tag and platform-specific download URL."""
        try:
            api_url = "https://api.github.com/repos/SteamRE/DepotDownloader/releases/latest"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            tag_name = data.get('tag_name', 'unknown')
            
            for asset in data.get('assets', []):
                asset_name = asset.get('name', '')
                if self.platform_identifier in asset_name and asset_name.endswith('.zip'):
                    return tag_name, asset.get('browser_download_url')
            
            raise DependencyInstallationError(f"No asset found for platform '{self.platform_identifier}' in the latest release.")
        except requests.RequestException as e:
            raise DependencyInstallationError(f"Failed to fetch latest version from GitHub: {e}")

    def _get_local_version(self) -> str | None:
        if not self.version_file.exists(): return None
        return self.version_file.read_text().strip()

    def _update_local_version(self, version: str):
        self.version_file.write_text(version)

    def ensure_dependencies(self) -> str:
        logging.info("Checking for DepotDownloader updates...")
        try:
            latest_version, download_url = self._get_latest_version()
        except DependencyInstallationError as e:
            logging.warning(f"Could not check for updates: {e}. Will use local version if available.")
            if self.executable_path.exists():
                return str(self.executable_path)
            raise e

        local_version = self._get_local_version()

        if local_version == latest_version and self.executable_path.exists():
            logging.info(f"DepotDownloader is up to date (version {local_version}).")
            return str(self.executable_path)

        logging.info(f"Downloading DepotDownloader version {latest_version} for {self.platform_identifier}...")
        zip_path = self.base_dir / 'depotdownloader.zip'
        
        try:
            with requests.get(download_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(zip_path, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            
            logging.info("Download complete. Extracting files...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.bin_dir)
            
            if platform.system() != "Windows":
                os.chmod(self.executable_path, 0o755)

            self._update_local_version(latest_version)
            logging.info(f"DepotDownloader installed successfully to: {self.bin_dir}")
        except Exception as e:
            raise DependencyInstallationError(f"Failed during download or extraction: {e}")
        finally:
            if os.path.exists(zip_path): os.remove(zip_path)

        if not self.executable_path.exists():
            raise DependencyInstallationError(f"{self.executable_name} not found after installation.")
            
        return str(self.executable_path)

manager = DependencyManager()