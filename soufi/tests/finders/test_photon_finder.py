# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import urllib
from unittest import mock

import requests
import testtools
from testtools.matchers._basic import SameMembers

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import photon
from soufi.testing import base


class BasePhotonTest(base.TestCase):
    def make_finder(self, name=None, version=None, **kwargs):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
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

    def make_index_page_content(self, name, version):
        # Makes something approximating the package index page from
        # vault.photon.org with our desired package at a random place.
        random_position = self.factory.randint(1, 8)
        rows = []
        for i in range(0, 10):
            if i == random_position:
                name_ = name
                version_ = version
            else:
                name_ = self.factory.make_string('name')
                version_ = self.factory.make_string('version')
            rows.append(self.make_href(f'{name_}-{version_}.src.rpm'))
        return b'\n'.join(row.encode('utf8') for row in rows)


class TestPhotonFinder(BasePhotonTest):
    def setUp(self):
        super().setUp()
        # Make sure this doesn't interfere with fast lookup tests.
        self.patch(photon.PhotonFinder, '_repo_lookup').return_value = None

    def test__get_dir(self):
        version = self.factory.make_string('version') + '.ph3'
        finder = self.make_finder(version=version)
        versions = ['1.0', '2.0', '3.0', '4.0', 'ignored']
        data = self.make_top_page_content(versions)
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        dir_ = finder._get_dir()
        self.assertEqual('3.0', dir_)
        get.assert_called_once_with(
            "https://packages.vmware.com/photon/", timeout=30
        )

    def test__get_dir_raises_on_multiple_answers(self):
        finder = self.make_finder()
        data = self.make_top_page_content(['1.0', '2.0'])
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        self.assertRaises(exceptions.SourceNotFound, finder._get_dir)
        get.assert_called_once_with(
            "https://packages.vmware.com/photon/", timeout=30
        )

    def test__get_path(self):
        finder = self.make_finder()
        data = self.make_index_page_content(finder.name, finder.version)
        ref = finder._get_path(data)
        self.assertEqual(f'{finder.name}-{finder.version}.src.rpm', ref)

    def test__get_path_returns_None_if_not_found(self):
        finder = self.make_finder()
        data = self.make_index_page_content(
            self.factory.make_string(), self.factory.make_string()
        )
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        dir_ = self.factory.make_string('8.0') + '/'
        self.assertIsNone(finder._get_path(dir_))

    def test_find_raises_when_not_found(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        self.patch(finder, '_get_dir').return_value = 'a'
        self.patch(finder, '_get_source_dirs_content').return_value = [
            (url, 'data')
        ]
        self.patch(finder, '_get_path').return_value = None
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.find()

    def test_find_raises_when_download_error(self):
        finder = self.make_finder()
        self.patch(requests, 'get').return_value = self.make_response(
            [], requests.codes.bad_request
        )
        with testtools.ExpectedException(exceptions.DownloadError):
            finder.find()

    def test_find(self):
        finder = self.make_finder()
        dir_ = self.factory.make_string('dir')
        url = self.factory.make_url()
        ref = self.factory.make_string()
        self.patch(finder, '_get_dir').return_value = dir_
        self.patch(finder, '_get_source_dirs_content').return_value = [
            (url, 'data')
        ]
        self.patch(finder, '_get_path').return_value = ref

        disc_source = finder.find()
        self.assertIsInstance(disc_source, photon.PhotonDiscoveredSource)
        self.assertEqual([f"{url}{ref}"], disc_source.urls)

    def test_find_calls_get_repo_if_using_fallback_method(self):
        finder = self.make_finder(version='1.2.3.ph4')
        url = self.factory.make_url()
        ref = self.factory.make_string()
        self.patch(finder, '_get_dir')
        content = [(url, 'a')]
        self.patch(finder, '_get_source_dirs_content').return_value = content
        self.patch(finder, '_repo_lookup').return_value = ref
        self.assertEqual(f'{url}{ref}', finder._find().urls[0])


class TestGetDirScenarios(BasePhotonTest):

    scenarios = [
        ('2.0', dict(version='2.0', append='.ph2')),
        ('3.0', dict(version='3.0', append='.ph3')),
        ('4.0', dict(version='4.0', append='.ph4')),
    ]

    def test__get_dir_ignores_dirs_based_on_package_version(self):
        # If the version has got a string like 'ph2' in it, then only look
        # in dirs starting with a 2. Same for ph4, etc.
        finder = self.make_finder()
        versions = ['2.0', '3.0', '4.0']
        data = self.make_top_page_content(versions)
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        finder.version += self.append
        dir = finder._get_dir()
        self.assertEqual(self.version, dir)


class TestGetSourceDirsContentScenarios(BasePhotonTest):
    def test_get_source_dirs_content(self):
        finder = self.make_finder()
        # Ensure irrelevant repo dirs are ignored with the 'bogus' one.
        repos = (
            '1_srpms_x86_64/',
            '2_srpms_x86_64/',
            '3_srpms_x86_64/',
            'bogus/',
        )
        expected_repos = repos[:2]
        top_data = self.make_top_page_content(repos)
        data = self.make_index_page_content(finder.name, finder.version)
        get = self.patch(requests, 'get')
        # Set up responses for the top index, and the packages indexes for each
        # item in repos. The '3' repo is a broken one which will get a 404.
        get.side_effect = (
            self.make_response(top_data, requests.codes.ok),
            self.make_response(data, requests.codes.ok),
            self.make_response(data, requests.codes.ok),
            self.make_response(b'', requests.codes.not_found),
        )
        dir_ = self.factory.make_string()
        # Consume iterator.
        yielded = [_ for _ in finder._get_source_dirs_content(dir_)]

        # We expect it to spit out pairs of (url, data), where each url is the
        # path to the eventual packages_dir that contains the package, and data
        # is the content of the page at that location.
        expected = [
            (
                f"{photon.PHOTON_PACKAGES}{dir_}{expected_os_dir}",
                data,
            )
            # Ensure only returned source dirs are considered.
            for expected_os_dir in expected_repos
        ]
        self.assertThat(yielded, SameMembers(expected))


class TestPhotonFinderRepoLookup(BasePhotonTest):
    def make_repo(self, evr, sourcerpm=None, location=None):
        repo = mock.MagicMock()
        findall = mock.MagicMock()
        repo.findall = findall
        package = mock.MagicMock()
        package.evr = evr
        package.sourcerpm = sourcerpm
        package.location = location
        findall.return_value = [package]
        return repo

    def test_returns_None_when_repo_load_fails(self):
        data = self.make_top_page_content(['updates'])
        finder = self.make_finder()
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        self.patch(finder, '_get_repo').return_value = None
        self.assertIsNone(finder._repo_lookup(self.factory.make_url()))

    def test_returns_None_when_package_not_found_in_repo(self):
        repo = self.make_repo(evr='')
        data = self.make_top_page_content(['updates'])
        finder = self.make_finder()
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        self.patch(finder, '_get_repo').return_value = repo
        self.assertIsNone(finder._repo_lookup(self.factory.make_url()))

    def test_returns_None_when_source_repo_load_fails(self):
        finder = self.make_finder()
        data = self.make_top_page_content(['releases'])
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        get_repo = self.patch(finder, '_get_repo')
        get_repo.return_value = None
        url = self.factory.make_url()
        self.assertIsNone(finder._repo_lookup(url))
        get_repo.assert_called_once_with(url + 'releases')

    def test_returns_None_when_source_package_not_found_in_repo(self):
        finder = self.make_finder()
        data = self.make_top_page_content(['releases'])
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        repo = self.make_repo(evr=self.factory.make_string())
        get_repo = self.patch(finder, '_get_repo')
        get_repo.return_value = repo
        url = self.factory.make_url()
        self.assertIsNone(finder._repo_lookup(url))
        get_repo.assert_called_once_with(url + 'releases')

    def test_returns_url_when_source_package_is_found(self):
        finder = self.make_finder()
        data = self.make_top_page_content(['updates'])
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        srcrpm = (f'{finder.name}-{finder.version}.src.rpm',)
        repo = self.make_repo(evr=finder.version, sourcerpm=srcrpm)
        self.patch(finder, '_get_repo').return_value = repo
        # Will match the first source_dirs entry as we made the fake
        # repo match right away.
        self.assertEqual(srcrpm, finder._repo_lookup(self.factory.make_url()))

    def test__get_repo_returns_None_when_HTTPError(self):
        url = self.factory.make_url()
        load = self.patch(photon.repomd, 'load')
        load.side_effect = urllib.error.HTTPError(
            url, '404', 'foo', dict(), None
        )
        finder = self.make_finder()
        repo = finder._get_repo(url)
        self.assertIsNone(repo)

    def test__get_repo_returns_repo(self):
        load = self.patch(photon.repomd, 'load')
        load.return_value = mock.sentinel.REPO
        finder = self.make_finder()
        url = self.factory.make_url()
        repo = finder._get_repo(url)
        load.assert_called_once_with(url)
        self.assertEqual(repo, mock.sentinel.REPO)

    def test__get_repo_is_cached(self):
        load = self.patch(photon.repomd, 'load')
        url = self.factory.make_url()
        finder = self.make_finder()
        finder._get_repo(url)
        finder._get_repo(url)
        load.assert_called_once_with(url)


class TestPhotonDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return photon.PhotonDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        pds = self.make_discovered_source(url)
        self.assertEqual(url, repr(pds))

    def test_make_archive(self):
        pds = self.make_discovered_source()
        self.assertEqual(pds.make_archive, pds.remote_url_is_archive)
