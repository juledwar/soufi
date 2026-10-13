# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.


import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlparse

from soufi import exceptions, finder

MAVEN_SEARCH_URL = 'https://search.maven.org/solrsearch/select'
MAVEN_REPO_URL = 'https://search.maven.org/remotecontent'
MAVEN_CENTRAL_URL = 'https://repo.maven.apache.org/maven2'
LOG = logging.getLogger(__name__)


class JavaFinder(finder.SourceFinder):
    """Find Java source JARs.

    Uses the SOLR search at https://search.maven.org/

    :param group_id: Optional Maven groupId to narrow the search. Without
        this, the search may return versions from different artifacts that
        share the same artifactId.
    """

    distro = finder.SourceType.java.value

    def __init__(self, *args, group_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_id = group_id
        self.discovery_path = None

    def _find(self):
        source_url = self.get_source_url()
        return JavaDiscoveredSource(
            [source_url], timeout=self.timeout,
            discovery_path=self.discovery_path,
        )

    def _get_release_history(self):
        # Build query - if group_id is provided, filter by it to avoid
        # matching different artifacts with the same name.
        if self.group_id:
            query = f'g:{self.group_id} AND a:{self.name} l:sources'
        else:
            query = f'a:{self.name} l:sources'
        params = dict(
            q=query,
            rows=200,
            core='gav',
            wt='json',
            sort='timestamp asc',
        )
        try:
            data = self.get_url(MAVEN_SEARCH_URL, params=params).json()
        except exceptions.DownloadError:
            raise exceptions.SourceNotFound

        docs = data.get('response', {}).get('docs', [])
        history = []
        seen = set()
        for doc in docs:
            version = doc.get('v')
            if not version or version in seen:
                continue
            seen.add(version)
            timestamp = doc.get('timestamp')
            if timestamp is not None:
                # Search returns timestamp in milliseconds since epoch.
                timestamp = f"{int(timestamp)}"
            history.append(
                {
                    'version': version,
                    'published_at': timestamp,
                }
            )

        if history == []:
            raise exceptions.SourceNotFound

        history.sort(
            key=lambda h: (
                h['published_at'] is not None,
                h['published_at'] or "",
            )
        )
        return history

    def get_source_url(self):
        """Find a source JAR, then try SCM metadata for an exact artifact."""
        query = f'a:{self.name} AND v:{self.version} AND l:sources'
        if self.group_id:
            query = f'g:{self.group_id} AND ' + query
        params = dict(q=query, rows=1, core='gav', wt='json')
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
        record = next(
            (r for r in data.get('response', {}).get('docs', [])
             if self._matches_coordinates(r)),
            None,
        )
        checked_groups = set()
        if data.get('response', {}).get('docs') and not record:
            LOG.info(
                'Rejecting Maven sources result for %s:%s: coordinates do '
                'not match the requested artifact',
                self.name,
                self.version,
            )
        if record:
            checked_groups.add(record['g'])
            source_url = self._test_sources_jar(record['g'])
            if source_url:
                self.discovery_path = 'maven-sources-jar'
                return source_url

        # Search for the published artifact itself. Unlike the source-label
        # query, this can discover artifacts that do not publish a sources JAR.
        artifact_query = f'a:{self.name} AND v:{self.version}'
        if self.group_id:
            artifact_query = f'g:{self.group_id} AND ' + artifact_query
        try:
            artifact_data = self.get_url(
                MAVEN_SEARCH_URL,
                params=dict(q=artifact_query, rows=100, core='gav', wt='json'),
            ).json()
        except exceptions.DownloadError:
            raise exceptions.SourceNotFound

        records = [
            r for r in artifact_data.get('response', {}).get('docs', [])
            if self._matches_coordinates(r)
        ]
        if artifact_data.get('response', {}).get('docs') and not records:
            LOG.info(
                'Rejecting Maven artifact results for %s:%s: no exact '
                'coordinate match',
                self.name,
                self.version,
            )
        for artifact in records:
            group = artifact['g']
            if group not in checked_groups:
                checked_groups.add(group)
                source_url = self._test_sources_jar(group)
                if source_url:
                    self.discovery_path = 'maven-sources-jar'
                    return source_url
            source_url = self._source_from_pom(group)
            if source_url:
                self.discovery_path = 'maven-pom-github-tag-archive'
                return source_url

        raise exceptions.SourceNotFound

    def _matches_coordinates(self, record):
        """Reject broad Maven results that do not match the requested GAV."""
        return (
            record.get('a') == self.name
            and record.get('v') == self.version
            and bool(record.get('g'))
            and (not self.group_id or record.get('g') == self.group_id)
        )

    def _test_sources_jar(self, group_id):
        filepath = (
            f"{group_id.replace('.', '/')}/{self.name}/{self.version}/"
            f"{self.name}-{self.version}-sources.jar"
        )
        found = self.test_url(MAVEN_REPO_URL, params=dict(filepath=filepath))
        if not found:
            LOG.info('Maven sources JAR unavailable: %s', filepath)
        return found.url if found else None

    def _source_from_pom(self, group_id):
        pom_url = (
            f"{MAVEN_CENTRAL_URL}/{group_id.replace('.', '/')}/"
            f"{self.name}/{self.version}/{self.name}-{self.version}.pom"
        )
        try:
            response = self.get_url(pom_url)
            root = ET.fromstring(response.content)
        except (
            exceptions.DownloadError,
            ET.ParseError,
            TypeError,
            ValueError,
        ):
            return None

        def child_text(parent, name):
            if parent is None:
                return ''
            for child in parent:
                if child.tag.rsplit('}', 1)[-1] == name:
                    return (child.text or '').strip()
            return ''

        scm_element = next(
            (element for element in root.iter()
             if element.tag.rsplit('}', 1)[-1] == 'scm'),
            None,
        )
        project_element = next(
            (element for element in root.iter()
             if element.tag.rsplit('}', 1)[-1] == 'project'),
            None,
        )
        tag = child_text(scm_element, 'tag')
        scm_value = (
            child_text(scm_element, 'connection')
            or child_text(scm_element, 'developerConnection')
            or child_text(scm_element, 'url')
        )
        scm = self._github_repository(scm_value)
        # A project homepage is useful only when SCM is not declared.
        if not scm and not scm_value:
            scm = self._github_repository(child_text(project_element, 'url'))
        if not scm:
            LOG.info(
                'Rejecting Maven candidate %s:%s:%s: POM has no usable '
                'GitHub SCM',
                group_id,
                self.name,
                self.version,
            )
            return None

        tags = []
        if tag and tag.upper() not in ('HEAD', 'TRUNK', 'MASTER'):
            tags.append(tag)
        tags.extend([f'v{self.version}', self.version])
        seen = set()
        for candidate in tags:
            if candidate in seen:
                continue
            seen.add(candidate)
            encoded_tag = quote(candidate, safe='')
            url = (
                f'https://codeload.github.com/{scm}/tar.gz/refs/tags/'
                f'{encoded_tag}'
            )
            found = self.test_url(url)
            if found:
                return found.url
            LOG.info(
                'Rejecting GitHub source archive candidate %s: not reachable',
                url,
            )
        return None

    @staticmethod
    def _github_repository(value):
        if not value:
            return None
        value = value.strip()
        value = re.sub(r'^scm:[^:]+:', '', value)
        value = re.sub(r'^git\+', '', value)
        if value.startswith('git@github.com:'):
            path = value.split(':', 1)[1]
        else:
            parsed = urlparse(value)
            if parsed.hostname not in ('github.com', 'www.github.com'):
                return None
            path = parsed.path.lstrip('/')
        if path.endswith('.git'):
            path = path[:-4]
        path = path.strip('/')
        parts = path.split('/')
        valid_parts = all(
            re.fullmatch(r'[A-Za-z0-9_.-]+', part) for part in parts
        )
        if len(parts) != 2 or not valid_parts:
            return None
        return '/'.join(parts)


class JavaDiscoveredSource(finder.DiscoveredSource):
    """A discovered Java source package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    archive_extension = '.jar'

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Required by the base class but JARs are already ZIP files so there is
        # nothing to do.
        pass

    def __init__(
        self, urls, timeout=finder.DEFAULT_TIMEOUT, discovery_path=None
    ):
        super().__init__(urls, timeout=timeout)
        self.discovery_path = discovery_path
        if urls and urls[0].startswith('https://codeload.github.com/'):
            self.archive_extension = '.tar.gz'

    def __repr__(self):
        return self.urls[0]
