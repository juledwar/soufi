# Copyright (c) 2024 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from unittest import mock

import requests

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import crate
from soufi.testing import base


class TestCrateFinder(base.TestCase):
    def make_finder(self, name=None, version=None, index=None):
        if name is None:
            name = self.factory.make_string("name")
        if version is None:
            version = self.factory.make_string("version")
        kwargs = dict(name=name, version=version, s_type=SourceType.crate)
        if index is not None:
            kwargs["index"] = index
        return crate.CrateFinder(**kwargs)

    def test_get_source_url(self):
        finder = self.make_finder()
        get_index_dl = self.patch(finder, "get_index_dl")
        index_dl = self.factory.make_url()
        get_index_dl.return_value = index_dl

        get = self.patch_head_with_response(requests.codes.ok)
        found_url = finder.get_source_url()
        expected_url = (
            f"{index_dl}/{finder.name}/{finder.name}-{finder.version}.crate"
        )
        self.assertEqual(expected_url, found_url)
        call = mock.call(
            expected_url,
            timeout=30,
        )
        self.assertIn(call, get.call_args_list)

    def test_get_source_url_source_not_found(self):
        finder = self.make_finder()
        self.patch(
            finder, "get_index_dl"
        ).return_value = self.factory.make_url()
        # Crates index returns a 403 when the crate is not found. ¯\_(ツ)_/¯
        self.patch_head_with_response(requests.codes.forbidden)
        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)

    def test_get_index_dl(self):
        index = self.factory.make_url()
        finder = self.make_finder(index=index)
        get_url = self.patch(finder, "get_url")
        index = self.factory.make_url()
        get_url.return_value.json.return_value = {"dl": index}

        found_index = finder.get_index_dl()
        self.assertEqual(index, found_index)
        call = mock.call(f"{finder.index}config.json")
        self.assertIn(call, get_url.call_args_list)

    def test_get_index_dl_no_dl_key(self):
        finder = self.make_finder()
        get_url = self.patch(finder, "get_url")
        get_url.return_value.json.return_value = {}

        self.assertRaises(exceptions.DownloadError, finder.get_index_dl)

    def test_find(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        self.patch(finder, "get_source_url").return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, crate.CrateDiscoveredSource)
        self.assertEqual([url], disc_source.urls)


class TestCrateDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return crate.CrateDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        pds = self.make_discovered_source(url)
        self.assertEqual(url, repr(pds))

    def test_make_archive(self):
        cds = self.make_discovered_source()
        self.assertEqual(cds.make_archive, cds.remote_url_is_archive)
