# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import requests
import testtools

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import gem
from soufi.testing import base


class TestGemFinder(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return gem.GemFinder(name, version, SourceType.gem)

    def test_get_source_url(self):
        finder = self.make_finder()
        url = f'{gem.GEM_DOWNLOADS}{finder.name}-{finder.version}.gem'

        head = self.patch_head_with_response(requests.codes.ok)
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        head.assert_called_once_with(url, timeout=30)

    def test_get_source_info_raises_when_response_fails(self):
        self.patch_head_with_response(requests.codes.not_found)
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_find(self):
        url = self.factory.make_url()
        finder = self.make_finder()
        self.patch(finder, 'get_source_url').return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, gem.GemDiscoveredSource)
        self.assertEqual([url], disc_source.urls)


class TestGemDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return gem.GemDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        gem_discovered_source = self.make_discovered_source(url)
        self.assertEqual(url, repr(gem_discovered_source))

    def test_make_archive(self):
        gds = self.make_discovered_source()
        self.assertEqual(gds.make_archive, gds.remote_url_is_archive)
