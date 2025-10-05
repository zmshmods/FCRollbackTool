# Libraries/SteamDDLib/app/manifest_parser.py

import re
from dataclasses import dataclass, field

@dataclass
class ManifestFile:
    name: str
    size: int
    sha: str
    flags: int

@dataclass
class Manifest:
    depot_id: str
    manifest_id: str
    creation_date: str
    total_files: int
    total_chunks: int
    total_bytes: int
    total_compressed_bytes: int
    files: dict[str, ManifestFile] = field(default_factory=dict)

    @classmethod
    def from_file(cls, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return cls.from_string(content)

    @classmethod
    def from_string(cls, content: str):
        """Parses manifest data directly from a string in memory."""
        patterns = {
            "depot_id": re.search(r"Content Manifest for Depot (\d+)", content),
            "manifest_id": re.search(r"Manifest ID / date\s+:\s*(\d+)", content),
            "creation_date": re.search(r"\d+\s*/\s*(.+)", content),
            "total_files": re.search(r"Total number of files\s+:\s*(\d+)", content),
            "total_chunks": re.search(r"Total number of chunks\s+:\s*(\d+)", content),
            "total_bytes": re.search(r"Total bytes on disk\s+:\s*(\d+)", content),
            "total_compressed_bytes": re.search(r"Total bytes compressed\s+:\s*(\d+)", content)
        }

        if not all(patterns.values()):
            raise ValueError("Could not parse one or more manifest header fields.")

        manifest = cls(
            depot_id=patterns["depot_id"].group(1),
            manifest_id=patterns["manifest_id"].group(1),
            creation_date=patterns["creation_date"].group(1).strip(),
            total_files=int(patterns["total_files"].group(1)),
            total_chunks=int(patterns["total_chunks"].group(1)),
            total_bytes=int(patterns["total_bytes"].group(1)),
            total_compressed_bytes=int(patterns["total_compressed_bytes"].group(1)),
        )

        file_pattern = re.compile(
            r"^\s*(\d+)\s+\d+\s+([0-9a-fA-F]{40})\s+(\d+)\s+(.+?)\s*$",
            re.MULTILINE
        )

        for match in file_pattern.finditer(content):
            size, sha, flags, name = match.groups()
            if sha != '0' * 40:
                file_entry = ManifestFile(
                    name=name.strip().replace('\\', '/'),
                    size=int(size),
                    sha=sha,
                    flags=int(flags)
                )
                manifest.files[file_entry.name] = file_entry
        
        return manifest