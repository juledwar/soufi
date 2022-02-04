# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from unittest import mock

import requests
from testtools.matchers._basic import SameMembers

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import golang
from soufi.testing import base


class TestGolangFinder(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        kwargs = dict(
            name=name,
            version=version,
            s_type=SourceType.go,
        )
        return golang.GolangFinder(**kwargs)

    def patch_requests(self, method_name, code):
        method = self.patch(requests, method_name)
        response = requests.Response()
        response.status_code = code
        response.close = mock.MagicMock()
        method.return_value = response
        return method

    def test_raises_when_module_not_found(self):
        finder = self.make_finder()
        self.patch_requests(
            'head',
            code=requests.codes.not_found,
        )
        self.assertRaises(exceptions.SourceNotFound, finder.find)

    def test_finds_module(self):
        finder = self.make_finder()
        head = self.patch_requests('head', code=requests.codes.ok)
        source = finder.find()
        expected = [
            f"{golang.PUBLIC_PROXY}{finder.name.lower()}"
            f"/@v/{finder.version}.zip"
        ]
        self.assertThat(source.urls, SameMembers(expected))
        head.assert_called_once_with(expected[0], timeout=finder.timeout)

    def test_retries_with_get_if_head_fails(self):
        finder = self.make_finder()
        head = self.patch_requests('head', code=requests.codes.not_allowed)
        get = self.patch_requests('get', code=requests.codes.ok)
        source = finder.find()
        expected = [
            f"{golang.PUBLIC_PROXY}{finder.name.lower()}"
            f"/@v/{finder.version}.zip"
        ]
        self.assertThat(source.urls, SameMembers(expected))
        head.assert_called_once_with(expected[0], timeout=finder.timeout)
        get.assert_called_once_with(
            expected[0], stream=True, timeout=finder.timeout
        )


class TestGolangDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return golang.GolangDiscoveredSource([url])

    def test_make_archive(self):
        gds = self.make_discovered_source()
        self.assertEqual(gds.make_archive, gds.remote_url_is_archive)

    def test_repr(self):
        url = self.factory.make_url()
        gds = self.make_discovered_source(url=url)
        self.assertEqual(url, repr(gds))
