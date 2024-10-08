# Copyright (c) 2024 Cisco Systems, Inc. and its affiliates
# All rights reserved.


import defusedxml.lxml
import requests

from soufi import exceptions, finder

DEFAULT_INDEX = "https://pecl.php.net/"


class PHPPECL(finder.SourceFinder):
    """Find PHP PECL packages.

    Looks up the package in the PECL index and returns the URL for the package.
    """

    distro = finder.SourceType.phppecl.value

    def _find(self):
        source_url = self.get_source_url()
        return PHPPECLDiscoveredSource([source_url], timeout=self.timeout)

    def get_source_url(self):
        """Examine the index to find the source URL for the package.

        This is simply a matter of using the index's REST API to do a package
        query, and returning a URL contained in the returned XML data.
        """
        url = f"{DEFAULT_INDEX}rest/r/{self.name}/{self.version}.xml"
        # The returned XML document contains a <g> element with the URL.
        try:
            with requests.get(url, stream=True, timeout=30) as r:
                r.raw.decode_content = True
                xml = defusedxml.lxml.parse(r.raw)
            return xml.find('.//{*}g').text
        except Exception:
            raise exceptions.SourceNotFound


class PHPPECLDiscoveredSource(finder.DiscoveredSource):
    """A discovered Rust Crate package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    archive_extension = ".tgz"

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but PECL archives are already tarballs so
        # nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]
