# Copyright (c) 2024 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import io
from pathlib import Path
from unittest import mock

import requests

from soufi import exceptions, testing
from soufi import finder as base_finder
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
        finder = self.make_finder()
        url = self.factory.make_url()
        do_task = self.patch(base_finder, 'do_task')
        do_task.return_value = (url,)

        found_url = finder.get_source_url()

        self.assertEqual(url, found_url)
        do_task.assert_called_once_with(
            php_pecl.get_pecl_url,
            f"{php_pecl.DEFAULT_INDEX}rest/r/"
            f"{finder.name}/{finder.version}.xml",
        )

    def test_get_source_url_source_not_found(self):
        finder = self.make_finder()
        do_task = self.patch(base_finder, 'do_task')
        do_task.side_effect = exceptions.SourceNotFound
        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)

    def test_find(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        self.patch(finder, "get_source_url").return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, php_pecl.PHPPECLDiscoveredSource)
        self.assertEqual([url], disc_source.urls)


class TestPHPPECLHelpers(base.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.testing = Path(testing.__path__[0]) / 'data' / 'phppecl'

    def setUp(self):
        self.queue = mock.MagicMock()
        super().setUp()

    def test_get_pecl_url(self):
        # The test data uses this package at this version.
        url = self.factory.make_url()
        get = self.patch_get_with_response(requests.codes.ok)
        fp = open(self.testing / "ncurses_1.0.2.xml", "rb")
        self.addCleanup(fp.close)
        # Patch the get context manager to return the file stream.
        get.return_value.__enter__.return_value.raw = fp

        php_pecl.get_pecl_url(self.queue, url)

        expected_url = f"{php_pecl.DEFAULT_INDEX}get/ncurses-1.0.2"
        self.queue.put.assert_called_once_with((expected_url,))
        get.assert_called_once_with(url, stream=True, timeout=30)

    def test_get_pecl_url_http_error(self):
        url = self.factory.make_url()
        get = self.patch(requests, 'get')
        get.side_effect = requests.exceptions.HTTPError()

        php_pecl.get_pecl_url(self.queue, url)

        self.queue.put.assert_called_once_with(
            (get.side_effect,), timeout=php_pecl.PHPPECL.timeout
        )

    def test_get_pecl_url_unserializable_error(self):
        # Initializing the exception with a live file pointer will make it
        # refuse to serialize.
        url = self.factory.make_url()
        fp = io.BufferedReader(io.StringIO())
        get = self.patch(requests, 'get')
        get.side_effect = requests.exceptions.RequestException(fp)

        php_pecl.get_pecl_url(self.queue, url)

        self.queue.put.assert_called_once_with(
            (mock.ANY,), timeout=php_pecl.PHPPECL.timeout
        )
        self.assertIn(
            're-raising as plain Exception', str(self.queue.put.call_args)
        )


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
