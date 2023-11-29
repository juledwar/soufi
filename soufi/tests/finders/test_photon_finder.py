# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from unittest import mock

import requests

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import photon, yum
from soufi.testing import base


class BasePhotonTest(base.TestCase):
    def make_finder(self, name=None, version=None, **kwargs):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        if 'source_repos' not in kwargs:
            kwargs['source_repos'] = ['']
        if 'binary_repos' not in kwargs:
            kwargs['binary_repos'] = ['']
        return photon.PhotonFinder(name, version, SourceType.os, **kwargs)

    def make_response(self, data, code):
        fake_response = mock.MagicMock()
        fake_response.content = data
        fake_response.status_code = code
        return fake_response

    def make_href(self, text):
        return f'<a href="{text}">{text}</a>'

    def make_top_page_content(self, versions):
        links = [self.make_href(v) for v in versions]
        return "\n".join(links)


class TestPhotonFinder(BasePhotonTest):
    def test_find(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        self.patch(finder, 'get_source_url').return_value = url
        disc_source = finder.find()
        self.assertIsInstance(disc_source, yum.YumDiscoveredSource)
        self.assertEqual([url], disc_source.urls)

    def test__get_source_repos(self):
        finder = self.make_finder()
        # Ensure irrelevant repo dirs are ignored with the 'bogus' ones.
        top_repos = ('3.0/', '4.0/')
        repos = (
            '1_srpms_x86_64/',
            'bogus/',
            '2_srpms_x86_64/',
            '3_srpms_x86_64/',
            'also_bogus/',
            '4_srpms_x86_64/',
        )
        top_data = self.make_top_page_content(top_repos)
        page1 = self.make_top_page_content(repos[:3])
        page2 = self.make_top_page_content(repos[3:])
        get = self.patch(requests, 'get')
        # Set up responses for the top index, and the packages indexes for each
        # item in repos.
        get.side_effect = (
            self.make_response(top_data, requests.codes.ok),
            self.make_response(page1, requests.codes.ok),
            self.make_response(page2, requests.codes.ok),
        )
        result = finder.get_source_repos()
        expected = [
            photon.PHOTON_PACKAGES + '/' + top_repos[1] + repos[0],
            photon.PHOTON_PACKAGES + '/' + top_repos[1] + repos[2],
            photon.PHOTON_PACKAGES + '/' + top_repos[0] + repos[3],
            photon.PHOTON_PACKAGES + '/' + top_repos[0] + repos[5],
        ]
        self.assertEqual(expected, result)
        # fmt: off
        get.assert_has_calls(
            [
                mock.call(photon.PHOTON_PACKAGES, timeout=30),
                mock.call(photon.PHOTON_PACKAGES + '/' + top_repos[1], timeout=30),  # noqa: E501
                mock.call(photon.PHOTON_PACKAGES + '/' + top_repos[0], timeout=30),  # noqa: E501
            ]
        )
        # fmt: on

    def test__get_source_repos_top_level_failure_throws_exception(self):
        finder = self.make_finder()
        self.patch_get_with_response(requests.codes.not_found)
        self.assertRaises(exceptions.DownloadError, finder.get_source_repos)

    def test__get_source_repos_subdir_failure_omits_subdirs(self):
        finder = self.make_finder()
        top_data = self.make_top_page_content(['1.0/', '2.0/'])
        data = self.make_top_page_content(['1_srpms_x86_64/'])
        get = self.patch(requests, 'get')
        # The first index page listed is actually no good
        get.side_effect = (
            self.make_response(top_data, requests.codes.ok),
            self.make_response(b'', requests.codes.not_found),
            self.make_response(data, requests.codes.ok),
        )
        # We should only have one source repo directory available
        result = finder.get_source_repos()
        expected = [f"{photon.PHOTON_PACKAGES}/1.0/1_srpms_x86_64/"]
        self.assertEqual(expected, result)
        get.assert_has_calls(
            [
                mock.call(photon.PHOTON_PACKAGES, timeout=30),
                mock.call(photon.PHOTON_PACKAGES + '/2.0/', timeout=30),
                mock.call(photon.PHOTON_PACKAGES + '/1.0/', timeout=30),
            ]
        )

    def test__get_binary_repos(self):
        finder = self.make_finder()
        top_repos = ('3.0/', '4.0/')
        repos = (
            '1_srpms_x86_64/',
            'bogus/',
            '2_packages_x86_64/',
            '3_updates_x86_64/',
            'also_bogus/',
            '4_srpms_x86_64/',
        )
        top_data = self.make_top_page_content(top_repos)
        page1 = self.make_top_page_content(repos[:3])
        page2 = self.make_top_page_content(repos[3:])
        self.patch(finder, 'test_url').return_value = True
        get = self.patch(requests, 'get')
        # Set up responses for the top index, and the packages indexes for each
        # item in repos.
        get.side_effect = (
            self.make_response(top_data, requests.codes.ok),
            self.make_response(page1, requests.codes.ok),
            self.make_response(page2, requests.codes.ok),
        )
        expected = [
            photon.PHOTON_PACKAGES + '/' + top_repos[1] + repos[2],
            photon.PHOTON_PACKAGES + '/' + top_repos[0] + repos[3],
        ]
        result = finder.get_binary_repos()
        self.assertEqual(expected, result)
        # fmt: off
        get.assert_has_calls(
            [
                mock.call(photon.PHOTON_PACKAGES, timeout=30),
                mock.call(photon.PHOTON_PACKAGES + '/' + top_repos[1], timeout=30),  # noqa: E501
                mock.call(photon.PHOTON_PACKAGES + '/' + top_repos[0], timeout=30),  # noqa: E501
            ]
        )
        # fmt: on

    def test__get_binary_repos_top_level_failure_throws_exception(self):
        finder = self.make_finder()
        self.patch_get_with_response(requests.codes.not_found)
        self.assertRaises(exceptions.DownloadError, finder.get_binary_repos)

    def test__get_binary_repos_subdir_failure_omits_subdirs(self):
        finder = self.make_finder()
        top_data = self.make_top_page_content(['6.0/', '9.0/'])
        data = self.make_top_page_content(['1_base_x86_64'])
        self.patch(finder, 'test_url').return_value = True
        get = self.patch(requests, 'get')
        # The first index page listed is actually no good
        get.side_effect = (
            self.make_response(top_data, requests.codes.ok),
            self.make_response(b'', requests.codes.not_found),
            self.make_response(data, requests.codes.ok),
        )
        # We should only have one source repo directory available
        result = finder.get_binary_repos()
        expected = [f"{photon.PHOTON_PACKAGES}/6.0/1_base_x86_64"]
        self.assertEqual(expected, result)
        get.assert_has_calls(
            [
                mock.call(photon.PHOTON_PACKAGES, timeout=30),
                mock.call(photon.PHOTON_PACKAGES + '/9.0/', timeout=30),
                mock.call(photon.PHOTON_PACKAGES + '/6.0/', timeout=30),
            ]
        )

    def test__get_binary_repos_subdir_failure_omits_empty_repo_dirs(self):
        finder = self.make_finder()
        top_data = self.make_top_page_content(['6.0/', '9.0/'])
        data = self.make_top_page_content(['1_base_x86_64'])
        # All repos in the top content are available
        get = self.patch(requests, 'get')
        get.side_effect = (
            self.make_response(top_data, requests.codes.ok),
            self.make_response(data, requests.codes.ok),
            self.make_response(data, requests.codes.ok),
        )
        # The first repo candidate contains no repo data
        self.patch(finder, 'test_url').side_effect = (False, True)
        # We should only have one source repo directory available
        result = finder.get_binary_repos()
        expected = [f"{photon.PHOTON_PACKAGES}/6.0/1_base_x86_64"]
        self.assertEqual(expected, result)
        get.assert_has_calls(
            [
                mock.call(photon.PHOTON_PACKAGES, timeout=30),
                mock.call(photon.PHOTON_PACKAGES + '/9.0/', timeout=30),
                mock.call(photon.PHOTON_PACKAGES + '/6.0/', timeout=30),
            ]
        )

    def test__walk_source_repos(self):
        name = self.factory.make_string('name')
        version = self.factory.make_string('ver')
        urls = [self.factory.make_url() for _ in range(10)]
        finder = self.make_finder(source_repos=urls)
        test_url = self.patch(finder, 'test_url')
        test_url.side_effect = (False, False, True)
        # Ensure that it doesn't run the entire list once one has been found
        self.assertEqual(
            f"{urls[2]}/{name}-{version}.src.rpm",
            finder._walk_source_repos(name, version),
        )
        test_url.assert_has_calls(
            [mock.call(f"{url}/{name}-{version}.src.rpm") for url in urls[:3]]
        )

    def test__walk_source_repos_no_match_returns_none(self):
        name = self.factory.make_string('name')
        version = self.factory.make_string('ver')
        urls = [self.factory.make_url() for _ in range(3)]
        finder = self.make_finder(source_repos=urls)
        test_url = self.patch(finder, 'test_url')
        test_url.return_value = False
        self.assertIsNone(finder._walk_source_repos(name, version))
        test_url.assert_has_calls(
            [mock.call(f"{url}/{name}-{version}.src.rpm") for url in urls]
        )

    def test__walk_source_repos_one_arg_short_circuits(self):
        arg = self.factory.make_string()
        # Deliberately setup the mock wrong, this way if future code breaks
        # the short-circuit behaviour this will throw errors
        finder = self.make_finder(source_repos=[1, 2, 3])
        test_url = self.patch(finder, 'test_url')
        self.assertIsNone(finder._walk_source_repos(arg))
        test_url.assert_not_called()
