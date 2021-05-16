import requests

from sofi import exceptions, finder

DEFAULT_INDEX = 'https://pypi.org/pypi/'
API_TIMEOUT = 30  # seconds


class PythonFinder(finder.SourceFinder):
    """Find Python source dists.

    Traverses the supplied index, defaulting to the one at pypi.org.

    :param pyindex: optional Python index server; defaults to
        https://pypi.org/pypi/
    """

    distro = finder.SourceType.python.value

    def __init__(self, *args, **kwargs):
        self.index = kwargs.pop('pyindex', DEFAULT_INDEX)
        if self.index[-1] != '/':
            self.index += '/'
        super().__init__(*args, **kwargs)

    def _find(self):
        source_url = self.get_source_url()
        return PythonDiscoveredSource([source_url])

    def get_source_url(self):
        """Get the URL from the JSON info for the Python package."""
        url = f"{self.index}{self.name}/{self.version}/json"
        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code != requests.codes.ok:
            raise exceptions.SourceNotFound
        data = response.json()
        releases = data['releases']
        for version, release_data in releases.items():
            if version != self.version:
                continue
            for item in release_data:
                if item['packagetype'] == 'sdist':
                    return item['url']

        # It should not be possible to get here unless the JSON returned
        # from the index is corrupted.
        raise exceptions.SourceNotFound


class PythonDiscoveredSource(finder.DiscoveredSource):
    """A discovered Python sdist package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but sdists are already tarballs so
        # nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]
