# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.


from soufi import exceptions, finder

NPM_REGISTRY = 'https://registry.npmjs.org/'


class NPMFinder(finder.SourceFinder):
    """Find NPM source files.

    Traverses the repository at https://registry.npmjs.org/
    """

    distro = finder.SourceType.npm.value

    def _find(self):
        source_url = self.get_source_url()
        return NPMDiscoveredSource([source_url], timeout=self.timeout)

    def _get_release_history(self):
        url = f"{NPM_REGISTRY}{self.name}"
        try:
            data = self.get_url(url).json()
        except exceptions.DownloadError:
            raise exceptions.SourceNotFound

        versions = data.get('versions', {})
        times = data.get('time', {})
        history = []
        for version, timestamp in times.items():
            if version in ('created', 'modified'):
                continue
            if version not in versions:
                continue
            history.append(
                {
                    'version': version,
                    'published_at': timestamp,
                }
            )

        if history == [] and versions:
            history = [
                {
                    'version': version,
                    'published_at': None,
                }
                for version in versions
            ]
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
        """Get the URL from the JSON info for the NPM package."""
        url = f"{NPM_REGISTRY}{self.name}/{self.version}"
        try:
            data = self.get_url(url).json()
        except exceptions.DownloadError:
            raise exceptions.SourceNotFound
        return data['dist']['tarball']


class NPMDiscoveredSource(finder.DiscoveredSource):
    """A discovered NPM source package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    archive_extension = '.tar.gz'

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but NPMs are already tarballs so
        # nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]
