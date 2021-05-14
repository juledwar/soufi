import contextlib
import tempfile

import requests

from sofi import exceptions, finder

NPM_REGISTRY = 'https://registry.npmjs.org/'
API_TIMEOUT = 30  # seconds


class NPMFinder(finder.SourceFinder):
    """Find NPM source files.

    Traverses the repository at https://registry.npmjs.org/
    """

    distro = finder.SourceType.npm.value

    def _find(self):
        source_url = self.get_source_url()
        return NPMDiscoveredSource([source_url])

    def get_source_url(self):
        """Get the URL from the JSON info for the NPM package."""
        url = f"{NPM_REGISTRY}{self.name}/{self.version}"
        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code != requests.codes.ok:
            raise exceptions.SourceNotFound
        data = response.json()
        return data['dist']['tarball']


class NPMDiscoveredSource(finder.DiscoveredSource):
    """A discovered NPM source package."""

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but NPMs are already tarballs so
        # nothing to do.
        pass

    @contextlib.contextmanager
    def make_archive(self):
        """Yield a copy of the downloaded archive.

        Overrides the base class method since we don't need to re-make the
        archive from NPM. Simply downloads the NPM tarball and yields it.
        """
        with tempfile.TemporaryDirectory() as target_dir:
            [url] = self.urls
            _, download_file_name = url.rsplit('/', 1)
            tarfile_name = self.download_file(
                target_dir, download_file_name, url
            )
            with open(tarfile_name, 'rb') as fd:
                yield fd

    def __repr__(self):
        return self.urls[0]
