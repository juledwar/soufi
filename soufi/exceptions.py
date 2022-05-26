# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

"""All exceptions raised by Soufi."""


class SourceNotFound(Exception):
    """Raised when source cannot be located."""

    pass


class DownloadError(Exception):
    """Raised when source cannot be downloaded.

    This is most commonly raised due to HTTPError exceptions, so this will
    also surface the status code from the HTTP response as a convenience.
    """

    status_code = None

    def __init__(self, *args, **kwargs):
        for arg in args:
            try:
                self.status_code = arg.response.status_code
                break
            except AttributeError:
                continue
