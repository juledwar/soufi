# Copyright (c) 2024 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from pathlib import Path
from unittest import mock

import requests

from soufi import exceptions, testing
from soufi.finder import SourceType
from soufi.finders import php_pecl
from soufi.testing import base


class TestPHPPECLFinder(base.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.testing = Path(testing.__path__[0]) / 'data' / 'phppecl'

    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string("name")
        if version is None:
            version = self.factory.make_string("version")
        kwargs = dict(name=name, version=version, s_type=SourceType.phppecl)
        return php_pecl.PHPPECL(**kwargs)

    def test_get_source_url(self):
        # The test data uses this package at this version.
        finder = self.make_finder("ncurses", "1.0.2")
        get = self.patch_get_with_response(requests.codes.ok)
        fp = open(self.testing / "ncurses_1.0.2.xml", "rb")
        self.addCleanup(fp.close)
        # Patch the get context manager to return the file stream.
        get.return_value.__enter__.return_value.raw = fp

        found_url = finder.get_source_url()
        expected_url = (
            f"{php_pecl.DEFAULT_INDEX}get/{finder.name}-{finder.version}"
        )
        self.assertEqual(expected_url, found_url)
        call = mock.call(
            f"{php_pecl.DEFAULT_INDEX}rest/r/"
            f"{finder.name}/{finder.version}.xml",
            stream=True,
            timeout=30,
        )
        self.assertIn(call, get.call_args_list)

    def test_get_source_url_source_not_found(self):
        finder = self.make_finder()
        self.patch_get_with_response(requests.codes.not_found)
        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)

    def test_find(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        self.patch(finder, "get_source_url").return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, php_pecl.PHPPECLDiscoveredSource)
        self.assertEqual([url], disc_source.urls)


class TestPHPPECLDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return php_pecl.PHPPECLDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        ds = self.make_discovered_source(url)
        self.assertEqual(url, repr(ds))

    def test_make_archive(self):
        ds = self.make_discovered_source()
        self.assertEqual(ds.make_archive, ds.remote_url_is_archive)
