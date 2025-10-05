# Libraries/SteamDDLib/app/changelog.py

from dataclasses import dataclass, field, asdict
from .manifest_parser import Manifest, ManifestFile

@dataclass
class HeaderChanges:
    """Detailed comparison of manifest headers."""
    manifest_id: dict[str, str]
    creation_date: dict[str, str]
    total_files: dict[str, int]
    total_chunks: dict[str, int]
    total_bytes: dict[str, int]
    total_compressed_bytes: dict[str, int]

@dataclass
class Changelog:
    """Represents a detailed difference between two manifests."""
    depot_id: str
    header_changes: HeaderChanges
    added: list[ManifestFile] = field(default_factory=list)
    modified: list = field(default_factory=list) # {'old': ..., 'new': ...}
    deleted: list[ManifestFile] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

def generate_changelog(old_manifest: Manifest, new_manifest: Manifest) -> Changelog:
    
    header_changes = HeaderChanges(
        manifest_id={"old": old_manifest.manifest_id, "new": new_manifest.manifest_id},
        creation_date={"old": old_manifest.creation_date, "new": new_manifest.creation_date},
        total_files={"old": old_manifest.total_files, "new": new_manifest.total_files},
        total_chunks={"old": old_manifest.total_chunks, "new": new_manifest.total_chunks},
        total_bytes={"old": old_manifest.total_bytes, "new": new_manifest.total_bytes},
        total_compressed_bytes={"old": old_manifest.total_compressed_bytes, "new": new_manifest.total_compressed_bytes},
    )
    
    changelog = Changelog(
        depot_id=new_manifest.depot_id,
        header_changes=header_changes
    )

    old_files = set(old_manifest.files.keys())
    new_files = set(new_manifest.files.keys())

    for filename in new_files - old_files:
        changelog.added.append(new_manifest.files[filename])

    for filename in old_files - new_files:
        changelog.deleted.append(old_manifest.files[filename])

    for filename in old_files.intersection(new_files):
        old_file = old_manifest.files[filename]
        new_file = new_manifest.files[filename]

        if old_file.sha != new_file.sha or old_file.size != new_file.size:
            modified_entry = {
                "name": new_file.name,
                "changes": {}
            }
            
            if old_file.size != new_file.size:
                modified_entry["changes"]["size"] = {"old": old_file.size, "new": new_file.size}
            
            if old_file.sha != new_file.sha:
                modified_entry["changes"]["sha"] = {"old": old_file.sha, "new": new_file.sha}
            
            changelog.modified.append(modified_entry)
            
    return changelog