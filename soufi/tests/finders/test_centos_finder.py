# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import itertools

import requests

from soufi.finder import SourceType
from soufi.finders import centos, yum
from soufi.testing import base


class BaseCentosTest(base.TestCase):
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

    def test__get_dirs(self):
        finder = self.make_finder()
        top_repos = ('1.0.123', '2.1.3456', 'bogus', '3.7.89', '3')
        top_data = self.make_top_page_content(top_repos)
        get = self.patch_get_with_response(requests.codes.ok, top_data)
        result = list(finder._get_dirs())
        # Ensure that only the items we're interested in come back
        self.assertEqual(['3.7.89', '2.1.3456', '1.0.123'], result)
        get.assert_called_once_with(centos.VAULT, timeout=30)

    def test__get_source_repos(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.return_value = True
        result = list(finder.get_source_repos())
        expected = [
            f"{centos.VAULT}{dir}/{subdir}/Source/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_source_repos_optimal(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs, optimal_repos=True)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.return_value = True
        result = list(finder.get_source_repos())
        expected = [
            f"{centos.VAULT}{dir}/{subdir}/Source/"
            for dir in dirs
            for subdir in (centos.DEFAULT_SEARCH + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.return_value = True
        result = list(finder.get_binary_repos())
        expected = [
            f"{centos.VAULT}{dir}/{subdir}/x86_64/os/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_old_style(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.side_effect = itertools.cycle((False, True))
        result = list(finder.get_binary_repos())
        expected = [
            f"{centos.VAULT}{dir}/{subdir}/x86_64/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_using_mirror(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.side_effect = itertools.cycle((False, False, True))
        result = list(finder.get_binary_repos())
        expected = [
            f"{centos.MIRROR}{dir}/{subdir}/x86_64/os/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_old_style_using_mirror(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.side_effect = itertools.cycle((False, False, False, True))
        result = list(finder.get_binary_repos())
        expected = [
            f"{centos.MIRROR}{dir}/{subdir}/x86_64/"
            for dir in dirs
            for subdir in subdirs
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_optimal(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs, optimal_repos=True)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.return_value = True
        result = list(finder.get_binary_repos())
        expected = [
            f"{centos.VAULT}{dir}/{subdir}/x86_64/os/"
            for dir in dirs
            for subdir in (centos.DEFAULT_SEARCH + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_optimal_old_style(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs, optimal_repos=True)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.side_effect = itertools.cycle((False, True))
        result = list(finder.get_binary_repos())
        expected = [
            f"{centos.VAULT}{dir}/{subdir}/x86_64/"
            for dir in dirs
            for subdir in (centos.DEFAULT_SEARCH + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_optimal_using_mirror(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs, optimal_repos=True)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.side_effect = itertools.cycle((False, False, True))
        result = list(finder.get_binary_repos())
        expected = [
            f"{centos.MIRROR}{dir}/{subdir}/x86_64/os/"
            for dir in dirs
            for subdir in (centos.DEFAULT_SEARCH + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)

    def test__get_binary_repos_optimal_old_style_using_mirror(self):
        subdirs = [self.factory.make_string() for _ in range(3)]
        finder = self.make_finder(repos=subdirs, optimal_repos=True)
        dirs = [self.factory.make_string() for _ in range(3)]
        get_dirs = self.patch(finder, '_get_dirs')
        get_dirs.return_value = dirs
        test_url = self.patch(finder, 'test_url')
        test_url.side_effect = itertools.cycle((False, False, False, True))
        result = list(finder.get_binary_repos())
        expected = [
            f"{centos.MIRROR}{dir}/{subdir}/x86_64/"
            for dir in dirs
            for subdir in (centos.DEFAULT_SEARCH + centos.OPTIMAL_SEARCH)
        ]
        self.assertEqual(expected, result)
