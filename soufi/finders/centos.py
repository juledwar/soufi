# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import re
from typing import Iterable

# Bandit reports this as vulnerable but it's OK in lxml now,
# defusedxml's lxml support is deprecated as a result.
from lxml import html  # nosec

import soufi.finders.yum as yum_finder
from soufi import finder

VAULT = "https://vault.centos.org/centos"
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
MIRROR = "http://mirror.centos.org/centos"


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
        if not source_repos:
            source_repos = self._get_source_repos(repos, optimal_repos)
        if not binary_repos:
            binary_repos = self._get_binary_repos(repos, optimal_repos)
        super().__init__(
            *args,
            source_repos=source_repos,
            binary_repos=binary_repos,
            **kwargs,
        )

    def _get_dirs(self):
        """Get all the possible Vault dirs that could match."""
        content = self._get_url(VAULT)
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

    def _get_source_repos(self, subdirs: Iterable[str], optimal_repos: bool):
        """Determine which source search paths are valid.

        Spams the vault with HEAD requests and keeps the ones that hit.
        """
        source_repos = []
        for dir in self._get_dirs():
            for subdir in subdirs:
                url = f"{VAULT}/{dir}/{subdir}/Source/"
                if self._test_url(url + "repodata/"):
                    source_repos.append(url)
            if optimal_repos:
                for subdir in OPTIMAL_SEARCH:
                    url = f"{VAULT}/{dir}/{subdir}/Source/"
                    if self._test_url(url + "repodata/"):
                        source_repos.append(url)
        return source_repos

    def _get_binary_repos(self, subdirs: Iterable[str], optimal_repos: bool):
        """Determine which binary search paths are valid.

        Spams the vault with HEAD requests and keeps the ones that hit.
        """
        binary_repos = []
        for dir in self._get_dirs():
            for subdir in subdirs:
                vault_url = f"{VAULT}/{dir}/{subdir}/x86_64/"
                mirror_url = f"{MIRROR}/{dir}/{subdir}/x86_64/"
                if self._test_url(vault_url + "os/repodata/"):
                    binary_repos.append(vault_url + "os/")
                elif self._test_url(vault_url + "repodata/"):
                    binary_repos.append(vault_url)
                elif self._test_url(mirror_url + "os/repodata/"):
                    binary_repos.append(mirror_url + "os/")
                elif self._test_url(mirror_url + "repodata/"):
                    binary_repos.append(mirror_url)
            if optimal_repos:
                for subdir in OPTIMAL_SEARCH:
                    vault_url = f"{VAULT}/{dir}/{subdir}/x86_64/"
                    mirror_url = f"{MIRROR}/{dir}/{subdir}/x86_64/"
                    if self._test_url(vault_url + "os/repodata/"):
                        binary_repos.append(vault_url + "os/")
                    elif self._test_url(vault_url + "repodata/"):
                        binary_repos.append(vault_url)
                    elif self._test_url(mirror_url + "os/repodata/"):
                        binary_repos.append(mirror_url + "os/")
                    elif self._test_url(mirror_url + "repodata/"):
                        binary_repos.append(mirror_url)

        return binary_repos
