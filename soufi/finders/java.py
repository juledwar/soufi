# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.


from soufi import exceptions, finder

MAVEN_SEARCH_URL = 'https://search.maven.org/solrsearch/select'
MAVEN_REPO_URL = 'https://search.maven.org/remotecontent'


class JavaFinder(finder.SourceFinder):
    """Find Java source JARs.

    Uses the SOLR search at https://search.maven.org/
    """

    distro = finder.SourceType.java.value

    def _find(self):
        source_url = self.get_source_url()
        return JavaDiscoveredSource([source_url], timeout=self.timeout)

    def get_source_url(self):
        """Construct a URL from the JSON response for the search."""
        params = dict(q=f'a:{self.name} v:{self.version} l:sources', rows=1)
        # NOTE(nic): empirical observation of throwing "bad" queries at this
        #  thing lead me to believe this will only ever return 200 OK unless
        #  the query string is literally corrupted; if you pass in a
        #  syntactically valid search string for a resource that does not
        #  exist, the response content simply contains a completely
        #  unrelated record.  :-(
        try:
            data = self.get_url(MAVEN_SEARCH_URL, params=params).json()
        except exceptions.DownloadError:
            raise exceptions.SourceNotFound

        # Transform the `group` attribute and use it to put together a
        # resource URL from the other data we have.  If it resolves, return
        # it, otherwise the previous search was no good.
        [record] = data['response']['docs']
        group = record['g'].replace('.', '/')
        params = dict(
            filepath=f'{group}/{self.name}/{self.version}/'
            f'{self.name}-{self.version}-sources.jar'
        )
        found = self.test_url(
            MAVEN_REPO_URL, params=params, allow_redirects=True
        )
        if not found:
            raise exceptions.SourceNotFound
        return found.url


class JavaDiscoveredSource(finder.DiscoveredSource):
    """A discovered Java source package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    archive_extension = '.jar'

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but JARs are already ZIP files so there is
        # nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]
