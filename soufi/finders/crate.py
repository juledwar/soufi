# Copyright (c) 2024 Cisco Systems, Inc. and its affiliates
# All rights reserved.


from soufi import exceptions, finder

DEFAULT_INDEX = "https://index.crates.io/"


class CrateFinder(finder.SourceFinder):
    """Find Rust Crates.

    Traverses the supplied index, defaulting to the one at index.crates.io.

    :param index: optional index server; defaults to
        https://index.crates.io/
    """

    distro = finder.SourceType.crate.value

    def __init__(self, *args, **kwargs):
        self.index = kwargs.pop("index", DEFAULT_INDEX)
        if self.index[-1] != "/":
            self.index += "/"
        super().__init__(*args, **kwargs)

    def _find(self):
        source_url = self.get_source_url()
        return CrateDiscoveredSource([source_url], timeout=self.timeout)

    def get_source_url(self):
        """Examine the index to find the source URL for the package.

        This is simply a matter of using the index's API to do a package query,
        and returning a computed URL for any exact match.

        Note: the Create index server's API does not do exact matches itself,
        so we need to iterate the results.
        """
        dl = self.get_index_dl()
        # This is a bit of a short cut and is assuming a particular file format
        # for each crate.  Nominally this is usually the case but we might
        # need to revist.
        url = f"{dl}/{self.name}/{self.name}-{self.version}.crate"
        if self.test_url(url):
            return url
        raise exceptions.SourceNotFound

    def get_index_dl(self):
        """Return the 'dl' value from the config.json at the index root."""
        # 'dl' is the URL prefix from which all downloads are made.
        config = self.get_url(f"{self.index}config.json").json()
        try:
            return config["dl"]
        except KeyError:
            raise exceptions.DownloadError(
                "Index is corrupt: No 'dl' key in index config.json"
            )


class CrateDiscoveredSource(finder.DiscoveredSource):
    """A discovered Rust Crate package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    archive_extension = ""  # .crate is part of the URL

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but Crates are already tarballs so
        # nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]
