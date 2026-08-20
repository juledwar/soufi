# Copyright (c) 2024 Cisco Systems, Inc. and its affiliates
# All rights reserved.


import pickle

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
        try:
            (source_url,) = self._cache.get_or_create(
                f"pecl-{url}",
                finder.do_task,
                creator_args=([get_pecl_url, url], {}),
            )
        except Exception:
            raise exceptions.SourceNotFound
        return source_url


class PHPPECLDiscoveredSource(finder.DiscoveredSource):
    """A discovered PHP PECL package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    archive_extension = ".tgz"

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but PECL archives are already tarballs so
        # nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]


# See: soufi.finders.yum.load_repomd, soufi.finders.yum.get_repomd
def get_pecl_url(queue, url):
    # The returned XML document contains a <g> element with the URL.
    timeout = PHPPECL.timeout
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raw.decode_content = True
            xml = defusedxml.lxml.parse(r.raw)
        source_url = xml.find('.//{*}g').text
    except Exception as e:
        try:
            pickle.dumps(e)
        except Exception:
            e = Exception(
                f"Could not serialize {e.__class__.__name__}, "
                f"re-raising as plain Exception with msg: {str(e)}"
            )
        queue.put((e,), timeout=timeout)
        return
    queue.put((source_url,))
