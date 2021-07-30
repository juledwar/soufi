# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
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

    def make_response(self, data, code):
        fake_response = mock.MagicMock()
        fake_response.json.return_value = data
        fake_response.status_code = code
        return fake_response

    def test_get_source_url(self):
        finder = self.make_finder()
        group = self.factory.make_string()
        url = self.factory.make_url()
        data = dict(response=dict(docs=[dict(g=group)]))

        get = self.patch(requests, 'get')
        head = self.patch(requests, 'head')
        get.return_value = self.make_response(data, requests.codes.ok)
        head.return_value = self.make_response(
            mock.MagicMock(), requests.codes.ok
        )
        head.return_value.url = url
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        expected = dict(
            q=f'a:{finder.name} v:{finder.version} l:sources', rows=1
        )
        get.assert_called_once_with(
            java.MAVEN_SEARCH_URL, params=expected, timeout=java.API_TIMEOUT
        )
        expected = dict(
            filepath=f'{group}/{finder.name}/{finder.version}/'
            f'{finder.name}-{finder.version}-sources.jar'
        )
        head.assert_called_once_with(
            java.MAVEN_REPO_URL,
            params=expected,
            allow_redirects=True,
            timeout=java.API_TIMEOUT,
        )

    def test_get_source_info_raises_when_get_response_fails(self):
        get = self.patch(requests, 'get')
        get.return_value = self.make_response([], requests.codes.bad)
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_get_source_info_raises_when_head_response_fails(self):
        group = self.factory.make_string()
        data = dict(response=dict(docs=[dict(g=group)]))
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        head = self.patch(requests, 'head')
        head.return_value = self.make_response([], requests.codes.not_found)
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
