import requests
from Core.Logger import logger

GITHUB_ACC = "zmshmods"
GITHUB_ACC_TOOL = "FCRollbackTool"
MAIN_REPO = "FCRollbackTool"
UPDATES_REPO = "FCRollbackToolUpdates"

class ToolUpdateManager:
    def __init__(self):
        self.TOOL_VERSION = "1.2.3 Beta"
        self.BUILD_VERSION = "6.5.10.2025"
        self.UPDATE_MANIFEST = f"https://raw.githubusercontent.com/{GITHUB_ACC}/{UPDATES_REPO}/main/toolupdate.json"
        self.CHANGELOG_BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_ACC}/{UPDATES_REPO}/main/Changelogs/"
        self._manifest_cache = {}
        self._changelog_cache = {}

    def getToolVersion(self) -> str:
        return self.TOOL_VERSION
    def getToolBulidVersion(self) -> str:
        return self.BUILD_VERSION

    def get_all_versions(self) -> list:
        if not self._manifest_cache:
            self.FetchManifests()
        return self._manifest_cache.get("ToolUpdate", {}).get("VersionHistory", [])

    def get_changelog_for_version(self, version: str) -> list:
        try:
            if version not in self._changelog_cache:
                response = requests.get(f"{self.CHANGELOG_BASE_URL}{version}.txt", timeout=10)
                response.raise_for_status()
                self._changelog_cache[version] = response.text.splitlines()
            return self._changelog_cache[version]
        except Exception as e:
            logger.error(f"Error fetching changelog for version {version}: {e}")
            return [f"- Unable to fetch changelog for v{version}"]
# --
    def FetchManifests(self) -> None:
        try:
            response = requests.get(self.UPDATE_MANIFEST, timeout=10)
            response.raise_for_status()
            self._manifest_cache = response.json()
            logger.debug("Fetched toolupdate manifest data")
        except Exception as e:
            logger.error(f"Error fetching manifest for toolupdate: {e}")
            self._manifest_cache = {}
    def getManifestToolVersion(self) -> str:
        if not self._manifest_cache:
            self.FetchManifests()
        return self._manifest_cache.get("ToolUpdate", {}).get("ToolVersion", "Unknown Version")
    def getManifestBuildVersion(self) -> str:
        if not self._manifest_cache:
            self.FetchManifests()
        return self._manifest_cache.get("ToolUpdate", {}).get("BulidVersion", "Unknown Build Version")
    def getMatchingVersion(self) -> bool:
        return self.getToolVersion() == self.getManifestToolVersion()
    def getToolChangelog(self) -> list:
        try:
            if self.TOOL_VERSION not in self._changelog_cache:
                response = requests.get(f"{self.CHANGELOG_BASE_URL}{self.TOOL_VERSION}.txt", timeout=10)
                response.raise_for_status()
                self._changelog_cache[self.TOOL_VERSION] = response.text.splitlines()
            return self._changelog_cache[self.TOOL_VERSION]
        except Exception as e:
            logger.error(f"Error fetching app changelog: {e}")
            return ["- Unable to fetch changelog"]
    def getDownloadUrl(self) -> str:
        if not self._manifest_cache:
            self.FetchManifests()
        return self._manifest_cache.get("ToolUpdate", {}).get("DownloadLink", None)
#--
    def getManifestChangelog(self) -> list:
        try:
            version = self.getManifestToolVersion()
            if version not in self._changelog_cache:
                response = requests.get(f"{self.CHANGELOG_BASE_URL}{version}.txt", timeout=10)
                response.raise_for_status()
                self._changelog_cache[version] = response.text.splitlines()
            return self._changelog_cache[version]
        except Exception as e:
            logger.error(f"Error fetching manifest changelog: {e}")
            return ["- Unable to fetch changelog"]