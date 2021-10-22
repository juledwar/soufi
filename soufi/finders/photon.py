# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

# TODO(nic): this and the CentOS finder share a lot of the same "bones".  It
#  may be worth refactoring them both to use common functionality.

import functools
import re
import urllib

# Bandit reports this as vulnerable but it's OK in lxml now,
# defusedxml's lxml support is deprecated as a result.
import repomd
import requests
from lxml import html  # nosec

from soufi import exceptions, finder

PHOTON_PACKAGES = "https://packages.vmware.com/photon/"
TIMEOUT = 30  # seconds


class PhotonFinder(finder.SourceFinder):
    """Find Photon source files.

    Iterates over the index at https://packages.vmware.com/photon/

    The lookup is a 2-stage process:
        1. A "fast" method of examining the index pages and looking for
           files that match the package name and version. This depends on
           the source package name being the same as the binary's and
           will cover ~70% of the look-ups.
        2. A slower fallback method, which downloads the repo's metadata
           and does a direct look-up of the source package name.
    """

    distro = finder.Distro.photon.value

    def _find(self):
        dir_ = self._get_dir()
        for url, dir_listing in self._get_source_dirs_content(dir_):
            ref = self._get_path(dir_listing)
            if ref:
                target_url = f"{url}{ref}"
                return PhotonDiscoveredSource([target_url])

        # If we get here, it's likely that the "fast" method has failed
        # because the source package name doesn't match the binary's. We
        # have one more way to look this up using the 'repomd' package
        ref = self._repo_lookup(f"{PHOTON_PACKAGES}{dir_}")
        if url and ref:
            return PhotonDiscoveredSource([f'{url}{ref}'])
        raise exceptions.SourceNotFound

    def _get_url(self, url):
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code != requests.codes.ok:
            raise exceptions.DownloadError(response.reason)
        return response.content

    def _get_dir(self, url=PHOTON_PACKAGES):
        """Get the relevant package dir."""
        content = self._get_url(url)
        tree = html.fromstring(content)
        dirs = tree.xpath('//a/text()')
        dirs = [d for d in dirs if d[0].isdigit()]

        # Do very basic checks to see if we can limit searched dirs based on
        # the package version containing a 'phN' hint.
        el = re.search(r'.ph(\d)', self.version)
        if el is not None:
            dirs = [d for d in dirs if d[0] == el.expand(r'\1')]

        # We should only have 1 candidate directory left.  If not, give up,
        # because something's gone wrong and we're not going to find it
        if len(dirs) != 1:
            raise exceptions.SourceNotFound
        return dirs[0]

    def _get_source_dirs_content(self, release_dir):
        """Yield all content from dirs under release_dir that have source.

        A Release dir is the dir under the top-level PHOTON_PACKAGES.
        Under there, there are many directories that can contain packages,
        and this function yields each in turn.
        """
        url = f"{PHOTON_PACKAGES}{release_dir}"
        content = self._get_url(url)
        tree = html.fromstring(content)
        # Ideally all the SRPM trees would have the exact same packages in
        # them, but their `aarch64` trees seem to be a little light.  Prefer
        # x86_64 to be safe
        dirs = tree.xpath(
            "//a[text()[contains(.,'srpms')][contains(.,'x86_64')]]/text()"
        )

        for dir_ in dirs:
            try:
                _url = f"{url}{dir_}"
                yield _url, self._get_url(_url)
            except exceptions.DownloadError:
                pass

    def _get_path(self, content):
        """Given a dir, see if it contains the source HREF."""
        # Grab source directory listing at dir and look for
        # <name>-<version>.src.rpm.
        tree = html.fromstring(content)
        href = f"{self.name}-{self.version}.src.rpm"
        ref = tree.xpath('//a[@href=$href]', href=href)
        if ref:
            return href
        return None

    def _repo_lookup(self, base_url):
        content = self._get_url(base_url)
        tree = html.fromstring(content)
        os_dirs = tree.xpath(
            "//a[contains(.,'updates') "
            "or contains(.,'release') "
            "or contains(.,'extras')]/text()"
        )
        for os_dir in os_dirs:
            bin_url = f"{base_url}{os_dir}"
            repo = self._get_repo(bin_url)
            if repo is None:
                break
            for package in repo.findall(self.name):
                if package.evr == self.version:
                    break
            else:
                continue
            return package.sourcerpm
        return None

    # Cache repo downloads as they are slow and network-bound.
    @classmethod
    @functools.lru_cache(maxsize=128)
    def _get_repo(cls, url):
        try:
            return repomd.load(url)
        except urllib.error.HTTPError:
            return None


class PhotonDiscoveredSource(finder.DiscoveredSource):
    """A discovered Photon source package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    archive_extension = '.src.rpm'

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Src RPMs are already compressed archives, nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]
