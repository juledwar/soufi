# Copyright (c) 2024 Cisco Systems, Inc. and its affiliates
# All rights reserved.


import requests

from soufi import exceptions, finder

DEFAULT_INDEX = "https://repo.packagist.org/"


class PHPComposer(finder.SourceFinder):
    """Find PHP Composer packages at the Packagist repo.

    Looks up the package in the Packagist repo and returns the URL for the
    package.
    """

    distro = finder.SourceType.phpcomposer.value

    def _find(self):
        source_url, extension = self.get_source_url()
        return PHPComposerDiscoveredSource(
            [source_url],
            timeout=self.timeout,
            archive_extension=f".{extension}",
        )

    def get_source_url(self):
        """Examine the repo to find the source URL for the package.

        Packagist has two APIs (see https://packagist.org/apidoc). The main one
        doesn't seem to allow queries for specific packages (nor at specific
        versions), so we can use repo.packagist.org optimistically by querying
        a known URL pattern at repo.packagist.org/p2/{package}.json. If the
        package exists, the metadata that is returned contains a list of all
        versions of the package that will need to be iterated to get the
        download URL.

        Note that the name of Composer packages usually takes the form of
        vendor/package, so the name of the package is the concatenation of
        these two parts.

        :return: A tuple of (URL, type) where the type is the archive_extension
            to use.
        """
        url = f"{DEFAULT_INDEX}p2/{self.name}.json"
        resp = requests.get(url, timeout=self.timeout)
        if resp.status_code != requests.codes.ok:
            raise exceptions.SourceNotFound

        versions = resp.json()["packages"][self.name]
        for version in versions:
            if self.version in (
                version["version"],
                version['version_normalized'],
            ):
                return version["dist"]["url"], version["dist"]["type"]

        raise exceptions.SourceNotFound


class PHPComposerDiscoveredSource(finder.DiscoveredSource):
    """A discovered PHP Composer package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive

    def __init__(self, *args, archive_extension, **kwargs):
        super().__init__(*args, **kwargs)
        self.archive_extension = archive_extension

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but PECL archives are already tarballs so
        # nothing to do.
        pass

    def __repr__(self):
        return f"{self.urls[0]}: {self.archive_extension}"
