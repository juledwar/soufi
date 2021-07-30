# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from unittest import mock

import requests
import testtools

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import npm
from soufi.testing import base


class TestNPMFinder(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return npm.NPMFinder(name, version, SourceType.npm)

    def make_response(self, data, code):
        fake_response = mock.MagicMock()
        fake_response.json.return_value = data
        fake_response.status_code = code
        return fake_response

    def test_get_source_url(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        data = dict(dist=dict(tarball=url))

        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        get.assert_called_once_with(
            f"https://registry.npmjs.org/{finder.name}/{finder.version}",
            timeout=30,
        )

    def test_get_source_info_raises_when_response_fails(self):
        get = self.patch(requests, 'get')
        get.return_value = self.make_response([], requests.codes.not_found)
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_find(self):
        url = self.factory.make_url()
        finder = self.make_finder()
        self.patch(finder, 'get_source_url').return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, npm.NPMDiscoveredSource)
        self.assertEqual([url], disc_source.urls)


class TestNPMDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return npm.NPMDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        nds = self.make_discovered_source(url)
        self.assertEqual(url, repr(nds))

    def test_make_archive(self):
        nds = self.make_discovered_source()
        self.assertEqual(nds.make_archive, nds.remote_url_is_archive)
