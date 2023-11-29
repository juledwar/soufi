# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from lxml import html

import soufi.exceptions
import soufi.finders.yum as yum_finder
from soufi import finder

PHOTON_PACKAGES = "https://packages.vmware.com/photon"


class PhotonFinder(yum_finder.YumFinder):
    """Find Photon source files.

    By default, Iterates over the index at https://packages.vmware.com/photon
    """

    distro = finder.Distro.photon.value

    def _get_dirs(self):
        content = self.get_url(PHOTON_PACKAGES).content
        tree = html.fromstring(content)
        retval = tree.xpath('//a/text()')
        return reversed([dir for dir in retval if dir[0].isdigit()])

    def _get_repos(self, xpath):
        dirs = []
        for release_dir in self._get_dirs():
            url = f"{PHOTON_PACKAGES}/{release_dir}"
            try:
                content = self.get_url(url).content
            except soufi.exceptions.DownloadError:
                continue
            tree = html.fromstring(content)
            # Ideally all the SRPM trees would have the exact same
            # packages in them, but their `aarch64` trees seem to be a
            # little light.  Prefer x86_64 to be safe
            dirs += [url + dir for dir in tree.xpath(xpath)]
        return dirs

    def get_source_repos(self):
        return self._get_repos(
            "//a[text()[contains(.,'srpms')][contains(.,'x86_64')]]/text()"
        )

    def get_binary_repos(self):
        """Retrieve a list of all repo URLs for binary RPM packages.

        Photon OS does not reliably publish repodata for all releases,
        so double-check all candidate repo dirs before using.
        """
        xpath = "//a[text()[not(contains(.,'srpms'))][contains(.,'x86_64')]]/text()"  # noqa: E501
        suffix = 'repodata/repomd.xml'
        return [r for r in self._get_repos(xpath) if self.test_url(r + suffix)]

    def _walk_source_repos(self, name, version=None):
        # Photon OS does not provide repomd.xml files for their source
        # repositories, so we need to override the wonderful source lookup
        # methods with...  this.

        # Short-circuit here to force a binary package lookup in the caller
        if version is None:
            return None

        # Re-assemble a source package name, and try to fetch it from all
        # the source repos.  This is startlingly effective.
        for repo in self.generate_source_repos():
            url = f"{repo.rstrip('/')}/{name}-{version}.src.rpm"
            if self.test_url(url):
                return url
        return None
