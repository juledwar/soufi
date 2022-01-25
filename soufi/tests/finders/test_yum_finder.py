# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.
import string
import urllib
from itertools import repeat
from unittest import mock

import repomd
import requests
from testtools.matchers import Equals, SameMembers

import soufi.exceptions
from soufi.finder import SourceType
from soufi.finders import yum
from soufi.testing import base


class YumFinderImpl(yum.YumFinder):
    """An implementation for testing the YumFimder ABC."""

    distro = 'yum'

    def get_source_repos(self):
        return ()

    def get_binary_repos(self):
        return ()


class BaseYumTest(base.TestCase):
    class FakePackage:
        vr = None
        evr = None
        location = None
        sourcerpm = None

        def __init__(self, vr=None, evr=None, location=None, sourcerpm=None):
            if vr is None:
                vr = BaseYumTest.factory.make_semver()
            if evr is None:
                evr = BaseYumTest.factory.make_semver()
            if location is None:
                location = BaseYumTest.factory.make_string()
            if sourcerpm is None:
                sourcerpm = BaseYumTest.factory.make_string()

            self.vr = vr
            self.evr = evr
            self.location = location
            self.sourcerpm = sourcerpm

    def make_finder(self, name=None, version=None, **kwargs):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        if 'source_repos' not in kwargs:
            kwargs['source_repos'] = []
        if 'binary_repos' not in kwargs:
            kwargs['binary_repos'] = []
        return YumFinderImpl(name, version, SourceType.os, **kwargs)

    def make_response(self, data, code):
        fake_response = mock.MagicMock()
        fake_response.content = data
        fake_response.status_code = code
        return fake_response

    def make_package(self, n=None, e=None, v=None, r=None, a=None, epoch=None):
        # `epoch` is `name` or `ver`, to denote where to inject it
        random_packagename = map(
            self.factory.random_choice,
            repeat(string.ascii_letters + string.digits + "_-"),
        )
        if n is None:
            n = self.factory.make_string(charset=random_packagename)
        if e is None:
            e = self.factory.randint(0, 10)
        if v is None:
            v = self.factory.make_semver()
        if r is None:
            r = self.factory.randint(0, 100)
        if a is None:
            a = self.factory.make_string()
        if epoch == 'ver':
            v = f"{e}:{v}"
        elif epoch == 'name':
            n = f"{e}:{n}"

        # Package names always end in `.rpm` for testing
        return f"{n}-{v}-{r}.{a}.rpm"


class TestYumFinder(BaseYumTest):
    def test_find(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        self.patch(finder, 'get_source_url').return_value = url
        disc_source = finder.find()
        self.assertIsInstance(disc_source, yum.YumDiscoveredSource)
        self.assertEqual([url], disc_source.urls)

    def test_generate_repos_with_plain_list(self):
        fallback = mock.MagicMock()
        finder = self.make_finder()
        repos = [self.factory.make_string() for _ in range(0, 3)]
        result = finder.generate_repos(repos, fallback)
        self.assertThat(result, SameMembers(repos))
        fallback.assert_not_called()

    def test_generate_repos_with_fallback(self):
        fallback = mock.MagicMock()
        repos_fallback = [self.factory.make_string() for _ in range(0, 3)]
        fallback.return_value = repos_fallback
        finder = self.make_finder()
        result = finder.generate_repos(None, fallback)
        self.assertThat(list(result), SameMembers(repos_fallback))

    def test_get_source_url(self):
        name = self.factory.make_string()
        url = self.factory.make_url()
        finder = self.make_finder(name=name)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_src.return_value = url
        self.patch(finder, 'test_url').return_value = True
        self.assertEqual(url, finder.get_source_url())
        walk_src.assert_called_once_with(name)

    def test_get_source_url_binary_package(self):
        name = self.factory.make_string()
        ver = self.factory.make_semver(extra=self.factory.make_string("-"))
        url = self.factory.make_url()
        finder = self.make_finder(name=name, version=ver)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_src.side_effect = (None, url)
        walk_binary = self.patch(finder, '_walk_binary_repos')
        walk_binary.return_value = name, ver
        self.patch(finder, 'test_url').return_value = True
        self.assertEqual(url, finder.get_source_url())
        walk_binary.assert_called_once_with(name)
        walk_src.assert_has_calls([mock.call(name), mock.call(name, ver)])

    def test_get_source_url_raises_on_no_source(self):
        name = self.factory.make_string()
        finder = self.make_finder(name=name)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_src.return_value = None
        self.assertRaises(
            soufi.exceptions.SourceNotFound, finder.get_source_url
        )
        walk_src.assert_called_once_with(name)

    def test_get_source_url_raises_on_no_source_2(self):
        name = self.factory.make_string()
        finder = self.make_finder(name=name)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_src.return_value = None
        walk_binary = self.patch(finder, '_walk_binary_repos')
        walk_binary.return_value = (name, None)
        self.assertRaises(
            soufi.exceptions.SourceNotFound, finder.get_source_url
        )
        walk_binary.assert_called_once_with(name)
        walk_src.assert_has_calls([mock.call(name), mock.call(name, None)])

    def test_get_source_url_raises_on_invalid_source(self):
        name = self.factory.make_string()
        url = self.factory.make_url()
        finder = self.make_finder(name=name)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_src.return_value = url
        self.patch(finder, 'test_url').return_value = False
        self.assertRaises(
            soufi.exceptions.SourceNotFound, finder.get_source_url
        )
        walk_src.assert_called_once_with(name)

    def test__walk_source_repos(self):
        src = [self.factory.make_url(), self.factory.make_url()]
        bin = [self.factory.make_url(), self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        repo = mock.MagicMock()
        repo.baseurl = self.factory.make_url()
        package = self.FakePackage(vr=finder.version)
        repo.findall.return_value = [package]
        self.patch(finder, '_get_repo').side_effect = (None, repo)
        self.patch(finder, 'test_url').return_value = False
        url = finder._walk_source_repos(finder.name)
        self.assertEqual(repo.baseurl + package.location, url)

    def test__walk_source_repos_different_version_hit(self):
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        repo = mock.MagicMock()
        repo.baseurl = self.factory.make_url()
        package = self.FakePackage()
        repo.findall.return_value = [package]
        self.patch(finder, '_get_repo').return_value = repo
        self.patch(finder, 'test_url').return_value = True
        url = finder._walk_source_repos(finder.name)
        self.assertEqual(repo.baseurl + package.location, url)

    def test__walk_source_repos_different_version_miss(self):
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        repo = mock.MagicMock()
        package = self.FakePackage()
        repo.findall.return_value = [package]
        self.patch(finder, '_get_repo').return_value = repo
        self.patch(finder, 'test_url').return_value = False
        url = finder._walk_source_repos(finder.name)
        self.assertIsNone(url)

    def test__walk_binary_repos(self):
        src = [self.factory.make_url(), self.factory.make_url()]
        bin = [self.factory.make_url(), self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        repo = mock.MagicMock()
        repo.baseurl = self.factory.make_url()
        n = self.factory.make_string()
        v = self.factory.make_semver()
        r = self.factory.randint(0, 100)
        srcrpm = self.make_package(n=n, v=v, r=r)
        package = self.FakePackage(vr=finder.version, sourcerpm=srcrpm)
        repo.findall.return_value = [package]
        self.patch(finder, '_get_repo').side_effect = (None, repo)
        name, version = finder._walk_binary_repos(finder.name)
        self.expectThat(name, Equals(n))
        self.expectThat(version, Equals(f"{v}-{r}"))

    def test__walk_binary_repos_no_sourcerpm(self):
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        repo = mock.MagicMock()
        package = self.FakePackage(vr=finder.version, sourcerpm='')
        repo.findall.return_value = [package]
        self.patch(finder, '_get_repo').return_value = repo
        name, version = finder._walk_binary_repos(finder.name)
        self.assertIsNone(name)
        self.assertIsNone(version)

    def test__walk_binary_repos_different_name_multiple_versions(self):
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        repo = mock.MagicMock()
        package = self.FakePackage()
        repo.findall.return_value = [package, package]
        self.patch(finder, '_get_repo').return_value = repo
        name, version = finder._walk_binary_repos(finder.name)
        self.assertIsNone(name)
        self.assertIsNone(version)

    def test__walk_binary_repos_different_name_different_version(self):
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        repo = mock.MagicMock()
        n = self.factory.make_string()
        v = self.factory.make_semver()
        r = self.factory.randint(0, 100)
        srcrpm = self.make_package(n=n, v=v, r=r)
        package = self.FakePackage(sourcerpm=srcrpm)
        repo.findall.return_value = [package]
        self.patch(finder, '_get_repo').return_value = repo
        name, version = finder._walk_binary_repos(finder.name)
        self.expectThat(name, Equals(n))
        self.expectThat(version, Equals(f"{v}-{r}"))


class TestYumFinderHelpers(BaseYumTest):
    def test__nevra_or_none_returns_nevra(self):
        name = self.factory.make_string()
        ver = self.factory.make_semver()
        rel = self.factory.randint(0, 100)
        pkg = mock.MagicMock()
        pkg.sourcerpm = self.make_package(n=name, v=ver, r=rel)
        finder = self.make_finder()
        self.assertEqual((name, f"{ver}-{rel}"), finder._nevra_or_none(pkg))

    def test__nevra_or_none_returns_none(self):
        package = mock.MagicMock()
        package.sourcerpm = ''
        finder = self.make_finder()
        self.assertEqual((None, None), finder._nevra_or_none(package))

    def test__get_repo_returns_none(self):
        url = self.factory.make_url()
        rmd = self.patch(repomd, 'load')
        rmd.side_effect = urllib.error.HTTPError(None, None, None, None, None)
        finder = self.make_finder()
        self.assertIsNone(finder._get_repo(url))

    def test__get_nevra(self):
        filename = self.make_package()
        finder = self.make_finder()
        nevra = finder._get_nevra(filename)
        reassembled = "{name}-{ver}-{rel}.{arch}.rpm".format(**nevra)
        self.assertEqual(filename, reassembled)

    def test__get_nevra_epoch_in_ver(self):
        e = self.factory.randint(0, 10)
        filename = self.make_package(e=e, epoch='ver')
        finder = self.make_finder()
        nevra = finder._get_nevra(filename)
        reassembled = "{name}-{epoch}:{ver}-{rel}.{arch}.rpm".format(**nevra)
        self.assertEqual(filename, reassembled)

    def test__get_nevra_epoch_in_name(self):
        e = self.factory.randint(0, 10)
        filename = self.make_package(e=e, epoch='name')
        finder = self.make_finder()
        nevra = finder._get_nevra(filename)
        reassembled = "{epoch}:{name}-{ver}-{rel}.{arch}.rpm".format(**nevra)
        self.assertEqual(filename, reassembled)

    def test__test_url_true(self):
        url = self.factory.make_url()
        fake_req = self.patch(requests, 'head')
        fake_req.return_value = self.make_response('', requests.codes.ok)
        finder = self.make_finder()
        self.assertTrue(finder.test_url(url))

    def test__test_url_false(self):
        url = self.factory.make_url()
        fake_req = self.patch(requests, 'head')
        fake_req.return_value = self.make_response('', requests.codes.teapot)
        finder = self.make_finder()
        self.assertFalse(finder.test_url(url))

    def test__test_url_timeout(self):
        url = self.factory.make_url()
        self.patch(requests, 'head').side_effect = requests.exceptions.Timeout
        finder = self.make_finder()
        self.assertFalse(finder.test_url(url))


class TestYumsDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return yum.YumDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        yds = self.make_discovered_source(url)
        self.assertEqual(url, repr(yds))

    def test_make_archive(self):
        yds = self.make_discovered_source()
        self.assertEqual(yds.make_archive, yds.remote_url_is_archive)
