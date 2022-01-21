# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import itertools
from unittest import mock

import requests

from soufi.finder import SourceType
from soufi.finders import centos, yum
from soufi.testing import base


class BaseCentosTest(base.TestCase):
    def setUp(self):
        super().setUp()
        yum.YumFinder._get_repo.cache_clear()
        yum.YumFinder._get_url.cache_clear()

    def make_finder(self, name=None, version=None, **kwargs):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        if 'source_repos' not in kwargs:
            kwargs['source_repos'] = ['']
        if 'binary_repos' not in kwargs:
            kwargs['binary_repos'] = ['']
        return centos.CentosFinder(name, version, SourceType.os, **kwargs)

    def make_response(self, data, code):
        fake_response = mock.MagicMock()
        fake_response.content = data
        fake_response.status_code = code
        return fake_response

    def make_href(self, text):
        return f'<a href="{text}">{text}</a>'

    def make_td(self, href):
        return f'<td class="indexcolname">{href}</td>'

    def make_top_page_content(self, versions):
        links = [self.make_td(self.make_href(v)) for v in versions]
        return "\n".join(links)


class TestCentosFinder(BaseCentosTest):
    def test_find(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        self.patch(finder, 'get_source_url').return_value = url
        disc_source = finder.find()
        self.assertIsInstance(disc_source, yum.YumDiscoveredSource)
        self.assertEqual([url], disc_source.urls)

    def test_initializer_finds_repos_when_called_with_no_args(self):
        name = self.factory.make_string('name')
        version = self.factory.make_string('version')
        get_source_repos = self.patch(centos.CentosFinder, '_get_source_repos')
        get_binary_repos = self.patch(centos.CentosFinder, '_get_binary_repos')
        centos.CentosFinder(name, version, SourceType.os)
        get_source_repos.assert_called_once_with(centos.DEFAULT_SEARCH, False)
        get_binary_repos.assert_called_once_with(centos.DEFAULT_SEARCH, False)

    def test__get_dirs(self):
        finder = self.make_finder()
        top_repos = ('1.0.123', '2.1.3456', 'bogus', '3.7.89', '3')
        top_data = self.make_top_page_content(top_repos)
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(top_data, requests.codes.ok)
        result = list(finder._get_dirs())
        # Ensure that only the items we're interested in come back
        self.assertEqual([top_repos[3], top_repos[1], top_repos[0]], result)
        get.assert_called_once_with(centos.VAULT, timeout=30)

    def test__get_source_repos(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.return_value = True
        result = list(finder._get_source_repos(subdirs, False))
        expected = [
            f"{centos.VAULT}/{dir}/{subdir}/Source/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_source_repos_optimal(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.return_value = True
        result = list(finder._get_source_repos(subdirs, True))
        expected = [
            f"{centos.VAULT}/{dir}/{subdir}/Source/"
            for dir in dirs
            for subdir in (tuple(subdirs) + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.return_value = True
        result = list(finder._get_binary_repos(subdirs, False))
        expected = [
            f"{centos.VAULT}/{dir}/{subdir}/x86_64/os/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_old_style(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.side_effect = itertools.cycle((False, True))
        result = list(finder._get_binary_repos(subdirs, False))
        expected = [
            f"{centos.VAULT}/{dir}/{subdir}/x86_64/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_using_mirror(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.side_effect = itertools.cycle((False, False, True))
        result = list(finder._get_binary_repos(subdirs, False))
        expected = [
            f"{centos.MIRROR}/{dir}/{subdir}/x86_64/os/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_old_style_using_mirror(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.side_effect = itertools.cycle((False, False, False, True))
        result = list(finder._get_binary_repos(subdirs, False))
        expected = [
            f"{centos.MIRROR}/{dir}/{subdir}/x86_64/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_optimal(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.return_value = True
        result = list(finder._get_binary_repos(subdirs, True))
        expected = [
            f"{centos.VAULT}/{dir}/{subdir}/x86_64/os/"
            for dir in dirs
            for subdir in (tuple(subdirs) + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_optimal_old_style(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.side_effect = itertools.cycle((False, True))
        result = list(finder._get_binary_repos(subdirs, True))
        expected = [
            f"{centos.VAULT}/{dir}/{subdir}/x86_64/"
            for dir in dirs
            for subdir in (tuple(subdirs) + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_optimal_using_mirror(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.side_effect = itertools.cycle((False, False, True))
        result = list(finder._get_binary_repos(subdirs, True))
        expected = [
            f"{centos.MIRROR}/{dir}/{subdir}/x86_64/os/"
            for dir in dirs
            for subdir in (tuple(subdirs) + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_optimal_old_style_using_mirror(self):
        finder = self.make_finder()
        dirs = [self.factory.make_string() for _ in range(3)]
        subdirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, '_test_url')
        test_url.side_effect = itertools.cycle((False, False, False, True))
        result = list(finder._get_binary_repos(subdirs, True))
        expected = [
            f"{centos.MIRROR}/{dir}/{subdir}/x86_64/"
            for dir in dirs
            for subdir in (tuple(subdirs) + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)

    def test__walk_source_repos_reinits_generator(self):
        # Force the finder to use the generator workflow
        name = self.factory.make_string('name')
        version = self.factory.make_string('version')
        finder = self.make_finder(source_repos=None)
        super_method = self.patch(yum.YumFinder, '_walk_source_repos')
        generator_reinit = self.patch(finder, '_get_source_repos')
        # Ensure that a fresh generator is spawned before walking repos
        finder._walk_source_repos(name, version=version)
        super_method.assert_called_once_with(name, version=version)
        generator_reinit.assert_called_once_with(centos.DEFAULT_SEARCH, False)

    def test__walk_source_repos_does_not_reinit_generator(self):
        # The unit test default uses empty repo lists
        name = self.factory.make_string('name')
        version = self.factory.make_string('version')
        finder = self.make_finder()
        super_method = self.patch(yum.YumFinder, '_walk_source_repos')
        generator_reinit = self.patch(finder, '_get_source_repos')
        # Since there is no generator in play, no re-init should occur.
        finder._walk_source_repos(name, version=version)
        super_method.assert_called_once_with(name, version=version)
        generator_reinit.assert_not_called()

    def test__walk_binary_repos_reinits_generator(self):
        # Force the finder to use the generator workflow
        name = self.factory.make_string('name')
        finder = self.make_finder(binary_repos=None)
        super_method = self.patch(yum.YumFinder, '_walk_binary_repos')
        generator_reinit = self.patch(finder, '_get_binary_repos')
        # Ensure that a fresh generator is spawned before walking repos
        finder._walk_binary_repos(name)
        super_method.assert_called_once_with(name)
        generator_reinit.assert_called_once_with(centos.DEFAULT_SEARCH, False)

    def test__walk_binary_repos_does_not_reinit_generator(self):
        # The unit test default uses empty repo lists
        name = self.factory.make_string('name')
        finder = self.make_finder()
        super_method = self.patch(yum.YumFinder, '_walk_binary_repos')
        generator_reinit = self.patch(finder, '_get_binary_repos')
        # Since there is no generator in play, no re-init should occur.
        finder._walk_binary_repos(name)
        super_method.assert_called_once_with(name)
        generator_reinit.assert_not_called()
