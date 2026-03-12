# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

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

    def test_get_source_url(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        data = dict(dist=dict(tarball=url))

        get = self.patch_get_with_response(requests.codes.ok, json=data)
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        get.assert_called_once_with(
            f"https://registry.npmjs.org/{finder.name}/{finder.version}",
            timeout=finder.timeout,
        )

    def test_get_source_info_raises_when_response_fails(self):
        self.patch_get_with_response(requests.codes.not_found)
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

    def test_get_release_history(self):
        finder = self.make_finder(name=self.factory.make_string())
        data = {
            'versions': {'1.0.0': {}, '2.0.0': {}},
            'time': {
                'created': '2020-01-01T00:00:00.000Z',
                'modified': '2025-01-01T00:00:00.000Z',
                '1.0.0': '2024-01-01T00:00:00.000Z',
                '2.0.0': '2024-02-01T00:00:00.000Z',
            },
        }
        self.patch_get_with_response(requests.codes.ok, json=data)

        history = finder.get_release_history()
        self.assertEqual(
            ['1.0.0', '2.0.0'], [item['version'] for item in history]
        )

    def test_get_release_history_raises_when_request_fails(self):
        finder = self.make_finder(name=self.factory.make_string())
        self.patch_get_with_response(requests.codes.bad_request)
        self.assertRaises(
            exceptions.SourceNotFound,
            finder.get_release_history,
        )

    def test_get_release_history_falls_back_to_versions_when_time_empty(self):
        finder = self.make_finder(name=self.factory.make_string())
        data = {
            'versions': {'1.0.0': {}, '2.0.0': {}},
            'time': {},
        }
        self.patch_get_with_response(requests.codes.ok, json=data)

        history = finder.get_release_history()
        self.assertEqual(
            ['1.0.0', '2.0.0'], sorted(item['version'] for item in history)
        )

    def test_get_release_history_raises_when_no_versions(self):
        finder = self.make_finder(name=self.factory.make_string())
        data = {
            'versions': {},
            'time': {'2.0.0': '2024-02-01T00:00:00.000Z'},
        }
        self.patch_get_with_response(requests.codes.ok, json=data)
        self.assertRaises(
            exceptions.SourceNotFound,
            finder.get_release_history,
        )


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
