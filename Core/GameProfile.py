import os

class GameProfile():
    id: str
    display_name: str
    exe_name: str
    registry_key: str
    steam_app_id: int
    
    registry_value_name: str = "Install Dir"
    app_data_folder_name: str
    
    live_editor_registry_key: str
    live_editor_registry_value_name: str = "Install Dir"

    semver_relative_path = os.path.join("__Installer", "installerdata.xml")
    patch_version_relative_path = os.path.join("Patch", "layout.toc")
    supported_profiles = ["TitleUpdates", "SquadsUpdates"]
    squads_types = ["Squads", "FutSquads"]

    @property
    def version(self) -> str:
        return "".join(filter(str.isdigit, self.id))
        
    @property
    def settings_path(self) -> str:
        base_path = os.path.expandvars(r"%localappdata%")
        return os.path.join(base_path, self.app_data_folder_name, "settings")
        
    @property
    def live_tuning_path(self) -> str:
        base_path = os.path.expandvars(r"%localappdata%\Temp")
        return os.path.join(base_path, self.app_data_folder_name, "onlinecache0", "attribdb.bin")

    @property
    def mod_manager_profile_name(self) -> str:
        return self.id
    
    @property
    def fet_data_profile_name(self) -> str:
        return self.display_name
        
class FC24Profile(GameProfile):
    id = "FC24"
    display_name = "EA SPORTS FC 24"
    exe_name = "FC24.exe"
    registry_key = r"SOFTWARE\EA SPORTS\EA SPORTS FC 24"
    steam_app_id = 2195250
    
    app_data_folder_name = "FC 24"
    
    live_editor_registry_key = r"SOFTWARE\Live Editor\FC 24"
    live_editor_registry_value_name = "Data Dir"

    @property
    def settings_path(self) -> str:
        base_path = os.path.expanduser(r"~\Documents")
        return os.path.join(base_path, self.app_data_folder_name, "settings")

class FC25Profile(GameProfile):
    id = "FC25"
    display_name = "EA SPORTS FC 25"
    exe_name = "FC25.exe"
    registry_key = r"SOFTWARE\EA SPORTS\EA SPORTS FC 25"
    steam_app_id = 2669321
    
    app_data_folder_name = display_name
    
    live_editor_registry_key = r"SOFTWARE\Live Editor\FC 25"

class FC26Profile(GameProfile):
    id = "FC26"
    display_name = "EA SPORTS FC 26"
    exe_name = "FC26.exe"
    registry_key = r"SOFTWARE\EA SPORTS\EA SPORTS FC 26"
    steam_app_id = 3405690
    
    app_data_folder_name = display_name
    
    live_editor_registry_key = r"SOFTWARE\Live Editor\FC 26"

class GameProfileManager:
    def __init__(self):
        self._profiles = {
            "FC26": FC26Profile(),
            "FC25": FC25Profile(),
            "FC24": FC24Profile(),
        }

    def get_profile(self, game_id: str) -> GameProfile | None:
        return self._profiles.get(game_id)

    def get_profile_by_exe(self, exe_name: str) -> GameProfile | None:
        for profile in self.get_all_profiles():
            if profile.exe_name.lower() == exe_name.lower():
                return profile
        return None

    def get_all_profiles(self) -> list[GameProfile]:
        return list(self._profiles.values())