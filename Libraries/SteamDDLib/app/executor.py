# SteamDDLib/app/executor.py

import subprocess
from .exceptions import DepotDownloaderError

class CommandExecutor:
    """Handles the construction and execution of DepotDownloader commands."""

    def __init__(self, executable_path: str):
        self.executable_path = executable_path

    def _build_args(self, params: dict) -> list[str]:
        """Converts a dictionary of parameters to a list of command-line arguments."""
        args = []
        for key, value in params.items():
            if value is None:
                continue
            
            arg_name = '-' + key.replace('_', '-')
            
            if isinstance(value, bool) and value:
                args.append(arg_name)
            elif not isinstance(value, bool):
                args.extend([arg_name, str(value)])
        return args

    def run(self, params: dict, output_callback=None):
        """Executes a DepotDownloader command and streams the output."""
        command = [self.executable_path] + self._build_args(params)
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        full_output = []
        for line in iter(process.stdout.readline, ''):
            clean_line = line.strip()
            if output_callback and clean_line:
                output_callback(clean_line)
            full_output.append(clean_line)
        
        process.stdout.close()
        exit_code = process.wait()

        if exit_code != 0:
            raise DepotDownloaderError(
                "DepotDownloader process failed.",
                exit_code,
                "\n".join(full_output)
            )