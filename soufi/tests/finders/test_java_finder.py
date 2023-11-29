# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

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
        data = dict(response=dict(docs=[dict(g=group)]))

        get = self.patch_get_with_response(requests.codes.ok, json=data)
        head = self.patch_head_with_response(requests.codes.ok)
        head.return_value.url = url
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        expected = dict(
            q=f'a:{finder.name} v:{finder.version} l:sources', rows=1
        )
        get.assert_called_once_with(
            java.MAVEN_SEARCH_URL, params=expected, timeout=finder.timeout
        )
        expected = dict(
            filepath=f'{group}/{finder.name}/{finder.version}/'
            f'{finder.name}-{finder.version}-sources.jar'
        )
        head.assert_called_once_with(
            java.MAVEN_REPO_URL,
            params=expected,
            allow_redirects=True,
            timeout=finder.timeout,
        )

    def test_get_source_info_raises_when_get_response_fails(self):
        self.patch_get_with_response(requests.codes.bad)
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_get_source_info_raises_when_head_response_fails(self):
        group = self.factory.make_string()
        data = dict(response=dict(docs=[dict(g=group)]))
        self.patch_get_with_response(requests.codes.ok, json=data)
        self.patch_head_with_response(requests.codes.not_found)
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_get_source_info_raises_when_head_response_times_out(self):
        group = self.factory.make_string()
        data = dict(response=dict(docs=[dict(g=group)]))
        self.patch_get_with_response(requests.codes.ok, json=data)
        head = self.patch(requests, 'head')
        head.side_effect = requests.exceptions.Timeout
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_find(self):
        url = self.factory.make_url()
        finder = self.make_finder()
        self.patch(finder, 'get_source_url').return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, java.JavaDiscoveredSource)
        self.assertEqual([url], disc_source.urls)


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
