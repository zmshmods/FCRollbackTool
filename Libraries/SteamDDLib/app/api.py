# SteamDDLib/app/api.py

from .executor import CommandExecutor
from .manager import manager
from .exceptions import ExecutableNotFoundError
import os

class DepotDownloaderAPI:
    """A Python API wrapper for the DepotDownloader command-line tool."""

    def __init__(self, executable_path: str = None):
        if executable_path:
            if not os.path.exists(executable_path):
                 raise ExecutableNotFoundError(f"Provided executable path does not exist: {executable_path}")
            final_path = executable_path
        else:
            final_path = manager.ensure_dependencies()
        
        self._executor = CommandExecutor(final_path)

    def _execute_command(self, params: dict, output_callback=None):
        """Internal method to run commands."""
        self._executor.run(params, output_callback)

    def download_app(self, app: int, depot: int = None, manifest: int = None, **kwargs):
        """
        Downloads an app, optionally filtered by depot and manifest.
        """
        output_callback = kwargs.pop('output_callback', None)
        params = {'app': app, 'depot': depot, 'manifest': manifest, **kwargs}
        self._execute_command(params, output_callback)

    def download_workshop(self, app: int, pubfile: int = None, ugc: int = None, **kwargs):
        """
        Downloads a workshop file using either a PublishedFileId or UGC ID.
        """
        output_callback = kwargs.pop('output_callback', None)
        params = {'app': app, 'pubfile': pubfile, 'ugc': ugc, **kwargs}
        self._execute_command(params, output_callback)