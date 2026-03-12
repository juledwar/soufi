# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.


from soufi import exceptions, finder

GEM_DOWNLOADS = 'https://rubygems.org/downloads/'
GEM_VERSIONS_URL = 'https://rubygems.org/api/v1/versions/'


class GemFinder(finder.SourceFinder):
    """Find Gem files.

    Finds files at https://rubygems.org/downloads
    """

    distro = finder.SourceType.gem.value

    def _find(self):
        source_url = self.get_source_url()
        return GemDiscoveredSource([source_url], timeout=self.timeout)

    def _get_release_history(self):
        url = f'{GEM_VERSIONS_URL}{self.name}.json'
        try:
            data = self.get_url(url).json()
        except exceptions.DownloadError:
            raise exceptions.SourceNotFound

        history = []
        for item in data:
            version = item.get('number')
            if not version:
                continue
            history.append(
                {
                    'version': version,
                    'published_at': item.get('created_at'),
                }
            )
        if history == []:
            raise exceptions.SourceNotFound

        history.sort(
            key=lambda h: (
                h['published_at'] is None,
                h['published_at'] or "",
            )
        )
        return history

    def get_source_url(self):
        url = f"{GEM_DOWNLOADS}{self.name}-{self.version}.gem"
        if not self.test_url(url):
            raise exceptions.SourceNotFound
        return url


class GemDiscoveredSource(finder.DiscoveredSource):
    """A discovered Gem package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    # NOTE(nic): `distro` and `archive_extension` are the same,
    # so auto-output mode will name these things `.gem.gem`.  The
    # recommended workaround is to not use auto-output mode :-)
    archive_extension = '.gem'

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but Gems are already tarballs so
        # nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]
