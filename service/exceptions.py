"""Custom exceptions for IMDb Crawler."""

class S3UploadError(Exception):
    """Raised when an S3 upload fails."""
    def __init__(self, message: str):
        super().__init__(message)

class ConfigurationError(Exception):
    """Raised when there is a configuration issue."""
    def __init__(self, message: str):
        super().__init__(message)

class PipelineError(Exception):
    """Raised when the pipeline encounters an error."""
    def __init__(self, message: str):
        super().__init__(message)

class NetworkError(Exception):
    """Raised for network-related errors."""
    def __init__(self, message: str):
        super().__init__(message)

class HTTPStatusError(Exception):
    """Raised for HTTP status errors."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)

class ProgressSaveError(Exception):
    """Raised when saving progress fails."""
    def __init__(self, message: str):
        super().__init__(message)

class ProgressLoadError(Exception):
    """Raised when loading progress fails."""
    def __init__(self, message: str):
        super().__init__(message)

class FileFlushError(Exception):
    """Raised when flushing records to file fails."""
    def __init__(self, message: str):
        super().__init__(message)

class FileCloseError(Exception):
    """Raised when closing the file fails."""
    def __init__(self, message: str):
        super().__init__(message)