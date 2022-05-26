# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

"""All exceptions raised by Soufi."""


class SourceNotFound(Exception):
    """Raised when source cannot be located."""

    pass


class DownloadError(Exception):
    """Raised when source cannot be downloaded.

    This is most commonly raised due to HTTPError exceptions, so this will
    also surface the status code from any chained HTTP responses, as a
    convenience.
    """

    @property
    def status_code(self):
        for arg in self.args:
            try:
                return arg.response.status_code
            except AttributeError:
                continue
        return None
