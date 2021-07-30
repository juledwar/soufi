"""All exceptions raised by Soufi."""


class SourceNotFound(Exception):
    """Raised when source cannot be located."""

    pass


class DownloadError(Exception):
    """Raised when source cannot be downloaded."""

    pass
