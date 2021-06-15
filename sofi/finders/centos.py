# Bandit reports this as vulnerable but it's OK in lxml now,
# defusedxml's lxml support is deprecated as a result.
import requests
from lxml import html  # nosec

from sofi import exceptions, finder

VAULT = "https://vault.centos.org/"
TIMEOUT = 30  # seconds


class CentosFinder(finder.SourceFinder):
    """Find CentOS source files.

    Iterates over the index at https://vault.centos.org/
    """

    distro = finder.Distro.centos.value

    def _find(self):
        dirs = self._get_dirs()
        for dir_ in sorted(dirs, reverse=True):
            url = self._get_path(dir_)
            if url:
                return CentosDiscoveredSource([url])
        raise exceptions.SourceNotFound

    def _get_url(self, url, do_raise=True):
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code != requests.codes.ok:
            raise exceptions.DownloadError(response.reason)
        return response.content

    def _get_dirs(self):
        """Get all the possible Vault dirs that could match."""
        url = f"{VAULT}"
        content = self._get_url(url)
        tree = html.fromstring(content)
        dirs = tree.xpath('//td[@class="indexcolname"]/a/text()')
        return [d for d in dirs if d[0].isdigit()]

    def _get_path(self, dir_):
        """Given a dir on Vault, see if it contains the source HREF."""
        # Grab source directory listing at dir and look for
        # <name>-<version>.src.rpm.
        os_dir = "BaseOS" if dir_.startswith("8") else "os"
        url = f"{VAULT}{dir_}{os_dir}/Source/SPackages/"
        content = self._get_url(url)
        tree = html.fromstring(content)
        href = f"{self.name}-{self.version}.src.rpm"
        ref = tree.xpath('//a[@href=$href]', href=href)
        if ref:
            return f"{url}{href}"
        return None


class CentosDiscoveredSource(finder.DiscoveredSource):
    """A discovered Centos source package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    archive_extension = '.src.rpm'

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Src RPMs are already compressed archives, nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]
