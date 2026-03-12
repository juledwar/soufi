# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
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

    def test_raises_when_module_not_found(self):
        finder = self.make_finder()
        self.patch_head_with_response(requests.codes.not_found)
        self.assertRaises(exceptions.SourceNotFound, finder.find)

    def test_finds_module(self):
        finder = self.make_finder()
        head = self.patch_head_with_response(requests.codes.ok)
        source = finder.find()
        expected = [
            f"{golang.PUBLIC_PROXY}{finder.name.lower()}"
            f"/@v/{finder.version}.zip"
        ]
        self.assertThat(source.urls, SameMembers(expected))
        head.assert_called_once_with(
            expected[0], timeout=finder.timeout, allow_redirects=True
        )

    def test_retries_with_get_if_head_fails(self):
        finder = self.make_finder()
        head = self.patch_head_with_response(requests.codes.not_allowed)
        get = self.patch_get_with_response(requests.codes.ok)
        source = finder.find()
        expected = [
            f"{golang.PUBLIC_PROXY}{finder.name.lower()}"
            f"/@v/{finder.version}.zip"
        ]
        self.assertThat(source.urls, SameMembers(expected))
        head.assert_called_once_with(
            expected[0], timeout=finder.timeout, allow_redirects=True
        )
        get.assert_called_once_with(
            expected[0], stream=True, timeout=finder.timeout
        )

    def test_get_release_history(self):
        finder = self.make_finder()
        get = self.patch_get_with_response(requests.codes.ok)
        get.return_value.text = "v1.0.0\nv1.1.0\n"

        history = finder.get_release_history()
        self.assertEqual(
            ['v1.0.0', 'v1.1.0'], [item['version'] for item in history]
        )

    def test_get_release_history_reverses_when_latest_first(self):
        finder = self.make_finder()
        get = self.patch(requests, 'get')

        def fake_get(url, *args, **kwargs):
            response = mock.MagicMock()
            response.status_code = requests.codes.ok
            if url.endswith('/@v/list'):
                response.text = "v1.1.0\nv1.0.0\n"
            else:
                response.json.return_value = {'Version': 'v1.1.0'}
            return response

        get.side_effect = fake_get
        history = finder.get_release_history()
        self.assertEqual(
            ['v1.0.0', 'v1.1.0'], [item['version'] for item in history]
        )

    def test_get_release_history_raises_when_request_fails(self):
        finder = self.make_finder()
        self.patch_get_with_response(requests.codes.bad_request)
        self.assertRaises(
            exceptions.SourceNotFound,
            finder.get_release_history,
        )

    def test_get_release_history_raises_when_empty(self):
        finder = self.make_finder()
        get = self.patch_get_with_response(requests.codes.ok)
        get.return_value.text = "\n"
        self.assertRaises(
            exceptions.SourceNotFound,
            finder.get_release_history,
        )

    def test_get_release_history_handles_latest_download_error(self):
        finder = self.make_finder()
        get = self.patch(requests, 'get')

        def fake_get(url, *args, **kwargs):
            response = mock.MagicMock()
            response.status_code = requests.codes.ok
            if url.endswith('/@v/list'):
                response.text = "v1.0.0\nv1.1.0\n"
            else:
                response.raise_for_status.side_effect = requests.HTTPError
            return response

        get.side_effect = fake_get
        history = finder.get_release_history()
        self.assertEqual(
            ['v1.0.0', 'v1.1.0'], [item['version'] for item in history]
        )

    def test_get_latest_version_returns_none_on_download_error(self):
        finder = self.make_finder()
        get_url = self.patch(finder, 'get_url')
        get_url.side_effect = exceptions.DownloadError("boom")
        self.assertIs(None, finder._get_latest_version())


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
