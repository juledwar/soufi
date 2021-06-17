import functools
import urllib

# Bandit reports this as vulnerable but it's OK in lxml now,
# defusedxml's lxml support is deprecated as a result.
import repomd
import requests
from lxml import html  # nosec

from sofi import exceptions, finder

VAULT = "https://vault.centos.org/centos/"
TIMEOUT = 30  # seconds


class CentosFinder(finder.SourceFinder):
    """Find CentOS source files.

    Iterates over the index at https://vault.centos.org/

    The lookup is a 2-stage process:
        1. A "fast" method of examining the index pages and looking for
           files that match the package name and version. This depends on
           the source package name being the same as the binary's and
           will cover ~70% of the look-ups.
        2. A slower fallback method, which downloads the repo's metadata
           and does a direct look-up of the source package name.  This ONLY
           works on version 8 of Centos because the Vault doesn't keep
           binary repodata around for older releases.
    """

    distro = finder.Distro.centos.value

    def _find(self):
        dirs = self._get_dirs()
        # Prevent going back too far in history.
        for dir_ in sorted(dirs, reverse=True):
            try:
                url = self._get_path(dir_)
            except exceptions.DownloadError:
                break
            if url:
                return CentosDiscoveredSource([url])

        # If we get here, it's likely that the "fast" method has failed
        # because the source package name doesn't match the binary's. We
        # have one more way to look this up using the 'repomd' package,
        # but that only works for v8 packages as the repo data only
        # exists for that release on Vault.
        if 'el8' in self.version:
            url = self._repo_lookup()
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
        packages_dir = "SPackages"
        if int(dir_[0]) < 6 or dir_ in ('6.1/', '6.0/'):
            # Releases up to and including 6.1 use "Packages" as the dir
            # name, and then inexplicably they started using SPackages.
            packages_dir = "Packages"
        url = f"{VAULT}{dir_}{os_dir}/Source/{packages_dir}/"
        content = self._get_url(url)
        tree = html.fromstring(content)
        href = f"{self.name}-{self.version}.src.rpm"
        ref = tree.xpath('//a[@href=$href]', href=href)
        if ref:
            return f"{url}{href}"
        return None

    def _repo_lookup(self):
        os_dir = "BaseOS"
        source_url = f"{VAULT}/8/{os_dir}/Source"
        bin_url = f"{VAULT}/8/{os_dir}/x86_64/os"
        repo = self._get_repo(bin_url)
        if repo is None:
            return None
        for package in repo.findall(self.name):
            if package.evr == self.version:
                break
        else:
            return None
        source_nevra = package.sourcerpm
        # Chop the '.src.rpm' from the end.
        source_evr = source_nevra[:-8]
        source_name, source_version = source_evr.split('-', 1)
        src_repo = self._get_repo(source_url)
        if src_repo is None:
            return None
        for spackage in src_repo.findall(source_name):
            if spackage.evr == source_version:
                return f"{source_url}/{spackage.location}"
        return None

    # Cache repo downloads as they are slow and network-bound.
    @classmethod
    @functools.lru_cache(maxsize=128)
    def _get_repo(cls, url):
        try:
            return repomd.load(url)
        except urllib.error.HTTPError:
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
