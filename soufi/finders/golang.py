# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.


from soufi import exceptions, finder

PUBLIC_PROXY = 'https://proxy.golang.org/'


class GolangFinder(finder.SourceFinder):
    """Find Golang modules.

    A simple HEAD request is made to the Goproxy, which will indicate
    whether the module is available or not.

    The proxy used defaults to the public https://proxy.golang.org/.
    """

    distro = finder.SourceType.go.value

    def __init__(self, *args, goproxy=PUBLIC_PROXY, **kwargs):
        super().__init__(*args, **kwargs)
        self.goproxy = goproxy

    @property
    def original_url(self):
        # It seems as though the proxy only works if the name gets lower-cased.
        # So Github repos such as Shopify/sarama don't work as-is. This Is The
        # Go Way and it must not be questioned.
        return f"{self.goproxy}{self.name.lower()}/@v/{self.version}.zip"

    def _find(self):
        # Main entrypoint from the parent class.
        if self.test_url(self.original_url):
            return GolangDiscoveredSource(
                [self.original_url], timeout=self.timeout
            )
        raise exceptions.SourceNotFound()

    def _get_release_history(self):
        url = f"{self.goproxy}{self.name.lower()}/@v/list"
        try:
            response = self.get_url(url)
        except exceptions.DownloadError:
            raise exceptions.SourceNotFound

        history = []
        for line in response.text.splitlines():
            version = line.strip()
            if not version:
                continue
            history.append({'version': version, 'published_at': None})

        if history == []:
            raise exceptions.SourceNotFound
        latest_version = self._get_latest_version()
        if latest_version and history[0]['version'] == latest_version:
            history.reverse()
        return history

    def _get_latest_version(self):
        url = f"{self.goproxy}{self.name.lower()}/@latest"
        try:
            data = self.get_url(url).json()
        except exceptions.DownloadError:
            return None
        if not isinstance(data, dict):
            return None
        return data.get('Version') or data.get('version')


class GolangDiscoveredSource(finder.DiscoveredSource):
    """A discovered Golang source module."""

    archive_extension = '.zip'
    make_archive = finder.DiscoveredSource.remote_url_is_archive

    # We *might* want to add `Disable-Module-Fetch: true` to the download
    # headers as recommended by the docs. This is left as a future exercise as
    # needed.

    def populate_archive(self, *args, **kwargs):
        pass  # pragma: no cover

    def __repr__(self):
        return self.urls[0]
