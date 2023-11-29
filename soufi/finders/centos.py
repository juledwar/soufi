# Copyright (c) 2022-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import re
from typing import Iterable

from lxml import html

import soufi.finders.yum as yum_finder
from soufi import finder

VAULT = "https://vault.centos.org/centos/"
DEFAULT_SEARCH = ('BaseOS', 'os', 'updates', 'extras')
# Optimal search dirs considered a useful extended set to inspect in
# addition to the defaults.
OPTIMAL_SEARCH = ('AppStream', 'PowerTools', 'fasttrack')

# CentOS is adorable sometimes.  The current release on mirror.centos.org
# stores zero binary packages in the vault.  It does store all source
# packages, however.  So when looking up binary package repos,
# it is necessary to also check the main mirror when looking for the "current"
# releases.  Note that the connection is unencrypted, and no HTTPS endpoint
# is provided.
MIRROR = "http://mirror.centos.org/centos/"


class CentosFinder(yum_finder.YumFinder):
    """Find CentOS source files.

    By default, iterates over the index at https://vault.centos.org

    :param repos: An iterable of repo names in the [S]Packages directory of
        the source repo. E.g. 'os', 'extras', etc. If not specified,
        a default set of 'os', 'BaseOS', 'updates' and 'extras' are examined.
    :param optimal_repos: (bool) Override repos to select what is considered
        an optimal set to inspect. These are the above defaults, plus:
        'AppStream', 'PowerTools', 'fasttrack'
    """

    distro = finder.Distro.centos.value

    def __init__(
        self,
        *args,
        repos: Iterable[str] = None,
        optimal_repos: bool = False,
        source_repos: Iterable[str] = None,
        binary_repos: Iterable[str] = None,
        **kwargs,
    ):
        if not repos or optimal_repos is True:
            repos = DEFAULT_SEARCH
        self.repos = repos
        self.optimal_repos = optimal_repos
        super().__init__(
            *args,
            source_repos=source_repos,
            binary_repos=binary_repos,
            **kwargs,
        )

    def _get_dirs(self):
        """Get all the possible Vault dirs that could match."""
        content = self.get_url(VAULT).content
        tree = html.fromstring(content)
        dirs = tree.xpath('//td[@class="indexcolname"]/a/text()')
        # CentOS Vault is fond of symlinking the current point release to a
        # directory with just the major version number, e.g., `6.10/`->`6/`.
        # This means that such directories are inherently unstable and their
        # contents are subject to change without notice, so we'll ignore
        # them in favour of the "full" names.
        dirs = [dir.rstrip('/') for dir in dirs if re.match(r'\d+\.\d', dir)]

        # Walk the tree backwards, so that newer releases get searched first
        return reversed(dirs)

    def get_source_repos(self):
        """Determine which source search paths are valid.

        Spams the vault with HEAD requests and keeps the ones that hit.

        CentOS is *big*.  CentOS is old, and the layout of the historical
        repos in the vault is so sprawling, that on average it takes about
        2 minutes of wall-clock time just to figure out where all of the
        repos are, and then even more time to subsequently download them all.

        As such, this is implemented as a generator so that the methods in the
        YumFinder base class can "load as it goes", rather than having to
        do a ton of discovery up-front that might end up being wasted.
        Absolutely everything is cached, so the relative overhead of having
        to run the generator over when re-walking the list of repos is minimal.
        """
        for dir in self._get_dirs():
            for subdir in self.repos:
                url = f"{VAULT.rstrip('/')}/{dir}/{subdir}/Source/"
                if self.test_url(url + "repodata/"):
                    yield url
            if self.optimal_repos:
                for subdir in OPTIMAL_SEARCH:
                    url = f"{VAULT.rstrip('/')}/{dir}/{subdir}/Source/"
                    if self.test_url(url + "repodata/"):
                        yield url

    def get_binary_repos(self):
        """Determine which binary search paths are valid.

        Spams the vault with HEAD requests and keeps the ones that hit.

        This is also implemented as a generator.  See get_source_repos().
        """

        def _find_valid_repo_url(dir, subdir):
            vault_url = f"{VAULT.rstrip('/')}/{dir}/{subdir}/x86_64/"
            mirror_url = f"{MIRROR.rstrip('/')}/{dir}/{subdir}/x86_64/"
            for url in vault_url, mirror_url:
                if self.test_url(url + "os/repodata/"):
                    yield url + "os/"
                    break
                elif self.test_url(url + "repodata/"):
                    yield url
                    break

        for dir in self._get_dirs():
            for subdir in self.repos:
                yield from _find_valid_repo_url(dir, subdir)
            if self.optimal_repos:
                for subdir in OPTIMAL_SEARCH:
                    yield from _find_valid_repo_url(dir, subdir)
