# SteamDDLib/app/exceptions.py

class SteamDDLibError(Exception):
    """Base exception for all library-specific errors."""
    pass

class ExecutableNotFoundError(SteamDDLibError):
    """Raised when the DepotDownloader executable or a required runtime cannot be found."""
    pass

class DependencyInstallationError(SteamDDLibError):
    """Raised when automatic installation of a dependency fails."""
    pass

class DepotDownloaderError(SteamDDLibError):
    """
    Raised when the DepotDownloader process exits with a non-zero status code,
    indicating an error occurred during its execution.
    """
    def __init__(self, message: str, exit_code: int, output: str):
        super().__init__(message)
        self.exit_code = exit_code
        self.output = output

    def __str__(self):
        return f"{super().__str__()} (Exit Code: {self.exit_code})\n--- Output ---\n{self.output}"