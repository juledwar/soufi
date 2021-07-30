# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import functools
import re
import urllib
from typing import Iterable

# Bandit reports this as vulnerable but it's OK in lxml now,
# defusedxml's lxml support is deprecated as a result.
import repomd
import requests
from lxml import html  # nosec

from soufi import exceptions, finder

VAULT = "https://vault.centos.org/centos/"
TIMEOUT = 30  # seconds


class CentosFinder(finder.SourceFinder):
    """Find CentOS source files.

    Iterates over the index at https://vault.centos.org/

    :param repos: An iterable of repo names in the [S]Packages directory of
        the source repo. E.g. 'os', 'extras', etc. If not specified,
        a default set of 'os', 'BaseOS', 'updates' and 'extras' are examined.
    :param optimal_repos: (bool) Override repos to select what is considered
        an optimal set to inspect. These are the above defaults, plus:
        'AppStream', 'PowerTools', 'fasttrack'

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

    # List of default source directories in each release. These are the default
    # ones that are inspected for source, and are inspected in the order given
    # here, unless overridden in the constructor.
    # TODO: Allow searching subdirs under these source dirs. The code currently
    #   expects srpms directly under these.
    default_source_dirs = [
        'os/',
        'BaseOS/',
        'updates/',
        'extras/',
    ]

    # Optimal source dirs considered a useful extended set to inspect in
    # addition to the defaults.
    optimal_source_dirs = [
        'AppStream/',
        'os/',
        'BaseOS/',
        'PowerTools',
        'updates/',
        'extras/',
        'fasttrack/',
    ]

    def __init__(
        self,
        *args,
        repos: Iterable[str] = None,
        optimal_repos: bool = False,
        **kwargs,
    ):
        if optimal_repos:
            self.source_dirs = self.optimal_source_dirs
        elif repos is not None:
            self.source_dirs = [f"{repo}/" for repo in repos]
        else:
            self.source_dirs = self.default_source_dirs
        super().__init__(*args, **kwargs)

    def _find(self):
        dirs = self._get_dirs()
        # Start at the latest release and work backwards.
        for dir_ in sorted(dirs, reverse=True):
            for url, dir_listing in self._get_source_dirs_content(dir_):
                ref = self._get_path(dir_listing)
                if ref:
                    target_url = f"{url}/{ref}"
                    return CentosDiscoveredSource([target_url])

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

    def _get_url(self, url):
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
        dirs = [d for d in dirs if d[0].isdigit()]

        # Do very basic checks to see if we can limit searched dirs based on
        # the package version containing a 'elN' hint. Just look for 6/7/8
        # versions for now.
        el = re.search(r'.el([678])', self.version)
        if el is not None:
            dirs = [d for d in dirs if d[0] == el.expand(r'\1')]

        return dirs

    def _get_source_dirs_content(self, release_dir):
        """Yield all content from dirs under release_dir that have source.

        A Release dir is the dir under the top-level VAULT.
        For example, '8/', which when appended to VAULT gives:
            https://vault.centos.org/centos/8/
        Under there, there are many directories that can contain packages,
        and this function yields each in turn.
        """
        url = f"{VAULT}{release_dir}"
        content = self._get_url(url)
        tree = html.fromstring(content)
        dirs = tree.xpath('//td[@class="indexcolname"]/a/text()')
        packages_dir = "SPackages"
        if int(release_dir[0]) < 6 or release_dir in ('6.1/', '6.0/'):
            # Releases up to and including 6.1 use "Packages" as the dir
            # name, and then inexplicably they started using SPackages.
            packages_dir = "Packages"

        # Attempt to only look up in the most common directories, to save time.
        # (sets are not ordered, and we need to keep ordering, so cannot use
        # set intersection here)
        dirs = [d for d in dirs if d in self.source_dirs]

        for dir_ in dirs:
            try:
                _url = f"{url}{dir_}Source/{packages_dir}"
                yield _url, self._get_url(_url)
            except exceptions.DownloadError:
                pass

    def _get_path(self, content):
        """Given a dir on Vault, see if it contains the source HREF."""
        # Grab source directory listing at dir and look for
        # <name>-<version>.src.rpm.
        tree = html.fromstring(content)
        href = f"{self.name}-{self.version}.src.rpm"
        ref = tree.xpath('//a[@href=$href]', href=href)
        if ref:
            return href
        return None

    def _repo_lookup(self):
        for os_dir in self.source_dirs:
            source_url = f"{VAULT}8/{os_dir}Source"
            bin_url = f"{VAULT}8/{os_dir}x86_64/os"
            repo = self._get_repo(bin_url)
            if repo is None:
                break
            for package in repo.findall(self.name):
                if package.evr == self.version:
                    break
            else:
                break
            source_nevra = package.sourcerpm
            # Chop the '.src.rpm' from the end.
            source_evr = source_nevra[:-8]
            source_name, source_version = source_evr.split('-', 1)
            src_repo = self._get_repo(source_url)
            if src_repo is None:
                break
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
