# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.


import logging
import re
from urllib.parse import quote, urlparse

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from soufi import exceptions, finder

MAVEN_SEARCH_URL = 'https://search.maven.org/solrsearch/select'
MAVEN_REPO_URL = 'https://search.maven.org/remotecontent'
MAVEN_CENTRAL_URL = 'https://repo.maven.apache.org/maven2'
LOG = logging.getLogger(__name__)


def _github_repository(value):
    """Return owner/repository for a supported GitHub SCM URL."""
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
    path = path.strip('/')
    if path.endswith('.git'):
        path = path[:-4]
    parts = path.split('/')
    valid_parts = all(re.fullmatch(r'[A-Za-z0-9_.-]+', part) for part in parts)
    if len(parts) != 2 or not valid_parts:
        return None
    return '/'.join(parts)


def _child_text(parent, name):
    """Return a direct child value by local XML name, ignoring namespaces."""
    if parent is None:
        return ''
    for child in parent:
        if child.tag.rsplit('}', 1)[-1] == name:
            return (child.text or '').strip()
    return ''


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
            [source_url],
            timeout=self.timeout,
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
        data = self._search_maven(query)

        # Keep every exact group in Solr order: all source JARs must be checked
        # before a POM tag is considered, and a POM is safe only when its group
        # is unambiguous.
        source_records = [
            r
            for r in data.get('response', {}).get('docs', [])
            if self._matches_coordinates(r)
        ]
        source_groups = list(dict.fromkeys(r['g'] for r in source_records))
        checked_groups = set()
        for group in source_groups:
            checked_groups.add(group)
            source_url = self._test_sources_jar(group)
            if source_url:
                self.discovery_path = 'maven-sources-jar'
                return source_url
        if data.get('response', {}).get('docs') and not source_records:
            LOG.info(
                'Rejecting Maven sources result for %s:%s: coordinates do '
                'not match the requested artifact',
                self.name,
                self.version,
            )
        # Search for the published artifact itself. Unlike the source-label
        # query, this can discover artifacts that do not publish a sources JAR.
        artifact_query = f'a:{self.name} AND v:{self.version}'
        if self.group_id:
            artifact_query = f'g:{self.group_id} AND ' + artifact_query
        artifact_data = self._search_maven(artifact_query)

        records = [
            r
            for r in artifact_data.get('response', {}).get('docs', [])
            if self._matches_coordinates(r)
        ]
        if artifact_data.get('response', {}).get('docs') and not records:
            LOG.info(
                'Rejecting Maven artifact results for %s:%s: no exact '
                'coordinate match',
                self.name,
                self.version,
            )
        artifact_groups = list(dict.fromkeys(r['g'] for r in records))
        candidate_groups = list(dict.fromkeys(source_groups + artifact_groups))

        # A later artifact hit may still publish the real source JAR, so check
        # all exact candidate coordinates before accepting a looser SCM tag.
        for group in candidate_groups:
            if group in checked_groups:
                continue
            checked_groups.add(group)
            source_url = self._test_sources_jar(group)
            if source_url:
                self.discovery_path = 'maven-sources-jar'
                return source_url

        pom_group = self._unambiguous_pom_group(source_groups, artifact_groups)
        if pom_group:
            source_url = self._source_from_pom(pom_group)
            if source_url:
                self.discovery_path = 'maven-pom-github-tag-archive'
                return source_url

        raise exceptions.SourceNotFound

    def _unambiguous_pom_group(self, source_groups, artifact_groups):
        """Choose the only defensible Maven group for the POM fallback."""
        if self.group_id:
            if self.group_id in source_groups + artifact_groups:
                return self.group_id
            return None
        if len(source_groups) == 1:
            return source_groups[0]
        if not source_groups and len(artifact_groups) == 1:
            return artifact_groups[0]
        return None

    def _search_maven(self, query):
        """Return a Solr response for a Maven query or raise if unavailable."""
        # Solr can return unrelated records for a valid query with no hits, so
        # callers must still verify each returned coordinate.
        try:
            return self.get_url(
                MAVEN_SEARCH_URL,
                params=dict(q=query, rows=100, core='gav', wt='json'),
            ).json()
        except exceptions.DownloadError:
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

    def _source_from_pom(self, group_id, parent_depth=0):
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
            DefusedXmlException,
            TypeError,
            ValueError,
        ):
            return None
        return self._source_from_pom_root(root, group_id, parent_depth)

    def _source_from_pom_root(self, root, group_id, parent_depth):
        """Resolve a GitHub source archive from parsed Maven POM metadata."""

        scm_element = next(
            (
                element
                for element in root.iter()
                if element.tag.rsplit('}', 1)[-1] == 'scm'
            ),
            None,
        )
        project_element = next(
            (
                element
                for element in root.iter()
                if element.tag.rsplit('}', 1)[-1] == 'project'
            ),
            None,
        )
        tag = _child_text(scm_element, 'tag')
        scm_value = (
            _child_text(scm_element, 'connection')
            or _child_text(scm_element, 'developerConnection')
            or _child_text(scm_element, 'url')
        )
        scm = _github_repository(scm_value)
        if not scm and parent_depth < 2:
            source_url = self._source_from_parent(root, parent_depth)
            if source_url:
                return source_url
        # A project homepage is useful only when no usable SCM is declared.
        if not scm:
            scm = _github_repository(_child_text(project_element, 'url'))
        if not scm:
            LOG.info(
                'Rejecting Maven candidate %s:%s:%s: POM has no usable '
                'GitHub SCM',
                group_id,
                self.name,
                self.version,
            )
            return None

        return self._test_github_tags(scm, tag)

    def _source_from_parent(self, root, parent_depth):
        """Fetch a parent POM and resolve its SCM, up to the depth limit."""
        parent = next(
            (
                element
                for element in root.iter()
                if element.tag.rsplit('}', 1)[-1] == 'parent'
            ),
            None,
        )
        group = _child_text(parent, 'groupId')
        artifact = _child_text(parent, 'artifactId')
        version = _child_text(parent, 'version')
        if not all((group, artifact, version)):
            return None
        pom_url = (
            f"{MAVEN_CENTRAL_URL}/{group.replace('.', '/')}/"
            f"{artifact}/{version}/{artifact}-{version}.pom"
        )
        try:
            response = self.get_url(pom_url)
            parent_root = ET.fromstring(response.content)
        except (
            exceptions.DownloadError,
            ET.ParseError,
            DefusedXmlException,
            TypeError,
            ValueError,
        ):
            return None
        # Reuse the resolver for inherited SCM, with a small depth cap.
        return self._source_from_pom_root(parent_root, group, parent_depth + 1)

    def _test_github_tags(self, scm, tag):
        """Try explicit and version-based Git tags for a parsed Maven POM."""
        tags = []
        if (
            tag
            and not self._is_unresolved(tag)
            and tag.upper() not in ('HEAD', 'TRUNK', 'MASTER', 'MAIN')
        ):
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
    def _is_unresolved(value):
        """Identify Maven or Gradle style placeholders left in POM values."""
        return '${' in value or '@{' in value


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
        super().__init__(urls, timeout=timeout, discovery_path=discovery_path)
        if urls and urls[0].startswith('https://codeload.github.com/'):
            self.archive_extension = '.tar.gz'

    def __repr__(self):
        return self.urls[0]
