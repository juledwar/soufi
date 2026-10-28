# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from unittest import mock

import requests
import testtools

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import java
from soufi.testing import base


class TestJavaFinder(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return java.JavaFinder(name, version, SourceType.java)

    def test_get_source_url(self):
        finder = self.make_finder()
        group = self.factory.make_string()
        url = self.factory.make_url()
        source_data = dict(
            response=dict(
                docs=[dict(g=group, a=finder.name, v=finder.version)]
            )
        )
        source_response = mock.Mock()
        source_response.json.return_value = source_data
        get = self.patch(finder, 'get_url')
        get.return_value = source_response
        head = self.patch(finder, 'test_url')
        head.return_value = mock.Mock(url=url)
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        expected = dict(
            q=f'a:{finder.name} AND v:{finder.version} AND l:sources',
            rows=100,
            core='gav',
            wt='json',
        )
        self.assertEqual((java.MAVEN_SEARCH_URL,), get.call_args_list[0].args)
        self.assertEqual(expected, get.call_args_list[0].kwargs['params'])
        get.assert_called_once()
        self.assertEqual(1, head.call_count)

    def test_get_source_info_raises_when_get_response_fails(self):
        self.patch_get_with_response(requests.codes.bad)
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_falls_back_to_github_tag_from_exact_artifact_pom(self):
        finder = self.make_finder(name='example-library', version='2.4.1')
        response = mock.Mock()
        response.json.return_value = {'response': {'docs': []}}
        artifact_response = mock.Mock()
        artifact_response.json.return_value = {
            'response': {
                'docs': [
                    {'g': 'org.example', 'a': finder.name, 'v': finder.version}
                ]
            }
        }
        get_url = self.patch(finder, 'get_url')
        get_url.side_effect = [
            response,
            artifact_response,
            mock.Mock(
                content=b'<project><scm><connection>'
                b'scm:git:https://github.com/example/library.git'
                b'</connection><tag>v2.4.1</tag></scm></project>'
            ),
        ]
        found = mock.Mock(
            url=(
                'https://codeload.github.com/example/library/'
                'tar.gz/refs/tags/v2.4.1'
            )
        )
        test_url = self.patch(finder, 'test_url')
        test_url.side_effect = [False, False, found]

        source_url = finder.get_source_url()

        self.assertEqual(found.url, source_url)
        self.assertEqual('maven-pom-github-tag-archive', finder.discovery_path)
        self.assertEqual(3, test_url.call_count)
        self.assertIn('/refs/tags/v2.4.1', test_url.call_args_list[1].args[0])

    def test_rejects_mismatched_maven_search_result(self):
        finder = self.make_finder(name='wanted', version='1.0')
        response = mock.Mock()
        response.json.return_value = {
            'response': {
                'docs': [{'g': 'org.example', 'a': 'other', 'v': '1.0'}]
            }
        }
        artifact_response = mock.Mock()
        artifact_response.json.return_value = {'response': {'docs': []}}
        self.patch(finder, 'get_url').side_effect = [
            response,
            artifact_response,
        ]
        test_url = self.patch(finder, 'test_url')

        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)
        test_url.assert_not_called()

    def test_github_repository_requires_github_host_and_repository_path(self):
        self.assertIsNone(
            java._github_repository('https://example.com/owner/repo')
        )
        self.assertIsNone(java._github_repository('https://github.com/owner'))

    def test_github_repository_strips_git_suffix_after_trailing_slashes(self):
        self.assertEqual(
            'owner/repo',
            java._github_repository('https://github.com/owner/repo.git/'),
        )
        self.assertEqual(
            'owner/repo',
            java._github_repository('git@github.com:owner/repo.git/'),
        )

    def test_pom_inherits_scm_from_parent(self):
        finder = self.make_finder(name='child', version='2.0')
        child = mock.Mock(
            content=(
                b'<project><parent><groupId>org.example</groupId>'
                b'<artifactId>parent</artifactId><version>1.0</version>'
                b'</parent></project>'
            )
        )
        parent = mock.Mock(
            content=(
                b'<project><scm><connection>'
                b'scm:git:https://github.com/example/parent.git'
                b'</connection><tag>v2.0</tag></scm></project>'
            )
        )
        get_url = self.patch(finder, 'get_url')
        get_url.side_effect = [child, parent]
        archive = mock.Mock(url='https://example.com/source.tar.gz')
        test_url = self.patch(finder, 'test_url')
        test_url.return_value = archive

        self.assertEqual(
            archive.url, finder._source_from_pom('org.example.child')
        )
        self.assertEqual(
            'https://repo.maven.apache.org/maven2/org/example/child/child/'
            '2.0/child-2.0.pom',
            get_url.call_args_list[0].args[0],
        )
        self.assertEqual(
            'https://repo.maven.apache.org/maven2/org/example/parent/1.0/'
            'parent-1.0.pom',
            get_url.call_args_list[1].args[0],
        )

    def test_pom_does_not_probe_unresolved_or_floating_tags(self):
        finder = self.make_finder(name='child', version='2.0')
        response = mock.Mock(
            content=(
                b'<project><scm><connection>'
                b'https://github.com/example/project.git'
                b'</connection><tag>${project.version}</tag></scm></project>'
            )
        )
        self.patch(finder, 'get_url').return_value = response
        archive = mock.Mock(url='https://example.com/source.tar.gz')
        test_url = self.patch(finder, 'test_url')
        test_url.side_effect = [False, archive]

        self.assertEqual(archive.url, finder._source_from_pom('org.example'))
        self.assertNotIn(
            '${project.version}', test_url.call_args_list[0].args[0]
        )
        self.assertIn('/refs/tags/v2.0', test_url.call_args_list[0].args[0])

    def test_pom_does_not_probe_main_as_a_tag(self):
        finder = self.make_finder(name='child', version='2.0')
        response = mock.Mock(
            content=(
                b'<project><scm><connection>'
                b'https://github.com/example/project.git'
                b'</connection><tag>main</tag></scm></project>'
            )
        )
        self.patch(finder, 'get_url').return_value = response
        archive = mock.Mock(url='https://example.com/source.tar.gz')
        test_url = self.patch(finder, 'test_url')
        test_url.return_value = archive

        self.assertEqual(archive.url, finder._source_from_pom('org.example'))
        self.assertIn('/refs/tags/v2.0', test_url.call_args.args[0])

    def test_parent_pom_download_failure_uses_project_homepage(self):
        finder = self.make_finder(name='child', version='2.0')
        child = mock.Mock(
            content=(
                b'<project><parent><groupId>org.example</groupId>'
                b'<artifactId>parent</artifactId><version>1.0</version>'
                b'</parent><url>https://github.com/example/project</url></project>'
            )
        )
        get_url = self.patch(finder, 'get_url')
        get_url.side_effect = [child, exceptions.DownloadError('unavailable')]
        self.patch(finder, 'test_url').return_value = False

        self.assertIsNone(finder._source_from_pom('org.example.child'))

    def test_pom_without_scm_or_homepage_returns_none(self):
        finder = self.make_finder(name='child', version='2.0')
        response = mock.Mock(content=b'<project></project>')
        self.patch(finder, 'get_url').return_value = response

        self.assertIsNone(finder._source_from_pom('org.example'))

    def test_ambiguous_artifacts_do_not_use_a_pom_guess(self):
        finder = self.make_finder(name='client', version='1.0')
        source_response = mock.Mock()
        source_response.json.return_value = {'response': {'docs': []}}
        artifact_response = mock.Mock()
        artifact_response.json.return_value = {
            'response': {
                'docs': [
                    {'g': 'org.first', 'a': 'client', 'v': '1.0'},
                    {'g': 'org.second', 'a': 'client', 'v': '1.0'},
                ]
            }
        }
        self.patch(finder, 'get_url').side_effect = [
            source_response,
            artifact_response,
        ]
        self.patch(finder, '_test_sources_jar').return_value = None
        from_pom = self.patch(finder, '_source_from_pom')

        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)
        from_pom.assert_not_called()

    def test_checks_all_source_jars_before_trying_pom(self):
        finder = self.make_finder(name='client', version='1.0')
        source_response = mock.Mock()
        source_response.json.return_value = {
            'response': {
                'docs': [
                    {'g': 'org.example', 'a': 'client', 'v': '1.0'},
                ]
            }
        }
        artifact_response = mock.Mock()
        artifact_response.json.return_value = {
            'response': {
                'docs': [
                    {'g': 'org.example', 'a': 'client', 'v': '1.0'},
                    {'g': 'org.other', 'a': 'client', 'v': '1.0'},
                ]
            }
        }
        self.patch(finder, 'get_url').side_effect = [
            source_response,
            artifact_response,
        ]
        checked = []

        def test_jar(group):
            checked.append(group)
            return None

        self.patch(finder, '_test_sources_jar').side_effect = test_jar
        from_pom = self.patch(finder, '_source_from_pom')
        from_pom.return_value = 'https://example.com/source.tar.gz'

        self.assertEqual(
            'https://example.com/source.tar.gz', finder.get_source_url()
        )
        self.assertEqual(['org.example', 'org.other'], checked)
        from_pom.assert_called_once_with('org.example')

    def test_group_id_constrains_queries_and_pom_fallback(self):
        finder = java.JavaFinder(
            'client', '1.0', SourceType.java, group_id='org.example'
        )
        source_response = mock.Mock()
        source_response.json.return_value = {'response': {'docs': []}}
        artifact_response = mock.Mock()
        artifact_response.json.return_value = {
            'response': {
                'docs': [
                    {'g': 'org.example', 'a': 'client', 'v': '1.0'},
                ]
            }
        }
        get_url = self.patch(finder, 'get_url')
        get_url.side_effect = [source_response, artifact_response]
        self.patch(finder, '_test_sources_jar').return_value = None
        from_pom = self.patch(finder, '_source_from_pom')
        from_pom.return_value = 'https://example.com/source.tar.gz'

        self.assertEqual(
            'https://example.com/source.tar.gz', finder.get_source_url()
        )
        self.assertIn(
            'g:org.example', get_url.call_args_list[0].kwargs['params']['q']
        )
        self.assertIn(
            'g:org.example', get_url.call_args_list[1].kwargs['params']['q']
        )
        from_pom.assert_called_once_with('org.example')

    def test_group_id_without_matching_maven_coordinate_does_not_fallback(
        self,
    ):
        finder = java.JavaFinder(
            'client', '1.0', SourceType.java, group_id='org.example'
        )
        source_response = mock.Mock()
        source_response.json.return_value = {'response': {'docs': []}}
        artifact_response = mock.Mock()
        artifact_response.json.return_value = {'response': {'docs': []}}
        self.patch(finder, 'get_url').side_effect = [
            source_response,
            artifact_response,
        ]
        from_pom = self.patch(finder, '_source_from_pom')

        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)
        from_pom.assert_not_called()

    def test_returns_sources_jar_from_later_artifact_candidate(self):
        finder = self.make_finder(name='client', version='1.0')
        source_response = mock.Mock()
        source_response.json.return_value = {'response': {'docs': []}}
        artifact_response = mock.Mock()
        artifact_response.json.return_value = {
            'response': {
                'docs': [
                    {'g': 'org.first', 'a': 'client', 'v': '1.0'},
                    {'g': 'org.second', 'a': 'client', 'v': '1.0'},
                ]
            }
        }
        self.patch(finder, 'get_url').side_effect = [
            source_response,
            artifact_response,
        ]
        source_url = 'https://example.com/client-sources.jar'
        self.patch(finder, '_test_sources_jar').side_effect = [
            None,
            source_url,
        ]
        from_pom = self.patch(finder, '_source_from_pom')

        self.assertEqual(source_url, finder.get_source_url())
        from_pom.assert_not_called()

    def test_artifact_search_failure_raises_source_not_found(self):
        finder = self.make_finder()
        source_response = mock.Mock()
        source_response.json.return_value = {'response': {'docs': []}}
        self.patch(finder, 'get_url').side_effect = [
            source_response,
            exceptions.DownloadError('unavailable'),
        ]

        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)

    def test_artifact_search_rejects_mismatched_coordinates(self):
        finder = self.make_finder(name='wanted', version='1.0')
        source_response = mock.Mock()
        source_response.json.return_value = {'response': {'docs': []}}
        artifact_response = mock.Mock()
        artifact_response.json.return_value = {
            'response': {
                'docs': [
                    {'g': 'org.example', 'a': 'other', 'v': '1.0'},
                ]
            }
        }
        self.patch(finder, 'get_url').side_effect = [
            source_response,
            artifact_response,
        ]
        test_jar = self.patch(finder, '_test_sources_jar')
        from_pom = self.patch(finder, '_source_from_pom')

        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)
        test_jar.assert_not_called()
        from_pom.assert_not_called()

    def test_get_source_info_raises_when_head_response_fails(self):
        group = self.factory.make_string()
        finder = self.make_finder()
        data = dict(
            response=dict(
                docs=[dict(g=group, a=finder.name, v=finder.version)]
            )
        )
        self.patch_get_with_response(requests.codes.ok, json=data)
        self.patch_head_with_response(requests.codes.not_found)
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_get_source_info_raises_when_head_response_times_out(self):
        group = self.factory.make_string()
        finder = self.make_finder()
        data = dict(
            response=dict(
                docs=[dict(g=group, a=finder.name, v=finder.version)]
            )
        )
        self.patch_get_with_response(requests.codes.ok, json=data)
        head = self.patch(requests, 'head')
        head.side_effect = requests.exceptions.Timeout
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_find(self):
        url = self.factory.make_url()
        finder = self.make_finder()
        self.patch(finder, 'get_source_url').return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, java.JavaDiscoveredSource)
        self.assertEqual([url], disc_source.urls)

    def test_get_release_history(self):
        finder = self.make_finder(name=self.factory.make_string())
        data = {
            'response': {
                'docs': [
                    {'v': '2.0.0', 'timestamp': 2000},
                    {'v': '1.0.0', 'timestamp': 1000},
                ]
            }
        }
        self.patch_get_with_response(requests.codes.ok, json=data)

        history = finder.get_release_history()
        self.assertEqual(
            ['1.0.0', '2.0.0'], [item['version'] for item in history]
        )

    def test_get_release_history_sorts_none_timestamp_as_oldest(self):
        finder = self.make_finder(name=self.factory.make_string())
        data = {
            'response': {
                'docs': [
                    {'v': '4.0.2'},
                    {'v': '5.1.0.RELEASE', 'timestamp': 1514764800000},
                ]
            }
        }
        self.patch_get_with_response(requests.codes.ok, json=data)

        history = finder.get_release_history()
        self.assertEqual(
            ['4.0.2', '5.1.0.RELEASE'],
            [item['version'] for item in history],
        )

    def test_get_release_history_raises_when_request_fails(self):
        finder = self.make_finder(name=self.factory.make_string())
        self.patch_get_with_response(requests.codes.bad_request)
        self.assertRaises(
            exceptions.SourceNotFound,
            finder.get_release_history,
        )

    def test_get_release_history_raises_when_docs_filtered(self):
        finder = self.make_finder(name=self.factory.make_string())
        data = {
            'response': {
                'docs': [
                    {'v': ''},
                    {'v': ''},
                ]
            }
        }
        self.patch_get_with_response(requests.codes.ok, json=data)
        self.assertRaises(
            exceptions.SourceNotFound,
            finder.get_release_history,
        )

    def test_get_release_history_uses_group_id(self):
        name = self.factory.make_string()
        group_id = self.factory.make_string()
        finder = java.JavaFinder(
            name,
            self.factory.make_string(),
            SourceType.java,
            group_id=group_id,
        )
        data = {'response': {'docs': [{'v': '1.0.0', 'timestamp': 1000}]}}
        get = self.patch_get_with_response(requests.codes.ok, json=data)

        finder.get_release_history()
        call_args = get.call_args
        query = call_args.kwargs['params']['q']
        self.assertIn(f'g:{group_id}', query)
        self.assertIn(f'a:{name}', query)


class TestNPMDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return java.JavaDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        jds = self.make_discovered_source(url)
        self.assertEqual(url, repr(jds))

    def test_make_archive(self):
        jds = self.make_discovered_source()
        self.assertEqual(jds.make_archive, jds.remote_url_is_archive)
