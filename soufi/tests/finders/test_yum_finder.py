# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import io
import string
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
        ver = self.factory.make_semver(extra=self.factory.make_string("-"))
        url = self.factory.make_url()
        finder = self.make_finder(name=name, version=ver)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_src.return_value = url
        walk_binary = self.patch(finder, '_walk_binary_repos')
        walk_binary.return_value = name, ver
        self.patch(finder, 'test_url').return_value = True
        self.assertEqual(url, finder.get_source_url())
        walk_binary.assert_called_once_with(name)
        walk_src.assert_called_once_with(name, ver)

    def test_get_source_url_raises_on_no_binary_package(self):
        name = self.factory.make_string()
        finder = self.make_finder(name=name)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_binary = self.patch(finder, '_walk_binary_repos')
        walk_binary.return_value = (None, None)
        self.assertRaises(
            soufi.exceptions.SourceNotFound, finder.get_source_url
        )
        walk_binary.assert_called_once_with(name)
        walk_src.assert_not_called()

    def test_get_source_url_raises_on_binary_repomd_download_error(self):
        name = self.factory.make_string()
        finder = self.make_finder(name=name)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_binary = self.patch(finder, '_walk_binary_repos')
        walk_binary.side_effect = Exception()
        self.assertRaises(
            soufi.exceptions.DownloadError, finder.get_source_url
        )
        walk_binary.assert_called_once_with(name)
        walk_src.assert_not_called()

    def test_get_source_url_raises_on_no_source(self):
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
        walk_src.assert_called_once_with(name, None)

    def test_get_source_url_raises_on_invalid_source(self):
        name = self.factory.make_string()
        url = self.factory.make_url()
        finder = self.make_finder(name=name)
        walk_binary = self.patch(finder, '_walk_binary_repos')
        walk_binary.return_value = (name, None)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_src.return_value = url
        self.patch(finder, 'test_url').return_value = False
        self.assertRaises(
            soufi.exceptions.SourceNotFound, finder.get_source_url
        )
        walk_binary.assert_called_once_with(name)
        walk_src.assert_called_once_with(name, None)

    def test_get_source_url_raises_on_source_repomd_download_error(self):
        name = self.factory.make_string()
        finder = self.make_finder(name=name)
        walk_src = self.patch(finder, '_walk_source_repos')
        walk_src.side_effect = Exception()
        walk_binary = self.patch(finder, '_walk_binary_repos')
        walk_binary.return_value = (name, None)
        self.assertRaises(
            soufi.exceptions.DownloadError, finder.get_source_url
        )
        walk_binary.assert_called_once_with(name)
        walk_src.assert_called_once_with(name, None)

    def test__walk_source_repos(self):
        baseurl = self.factory.make_url()
        src = [self.factory.make_url(), self.factory.make_url()]
        bin = [self.factory.make_url(), self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        package = self.FakePackage(vr=finder.version)
        do_task = self.patch(yum, 'do_task')
        do_task.return_value = (baseurl, {finder.name: [package]})
        self.patch(finder, 'test_url').return_value = False
        url = finder._walk_source_repos(finder.name)
        self.assertEqual(baseurl + package.location, url)

    def test__walk_source_repos_different_version_hit(self):
        baseurl = self.factory.make_url()
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        package = self.FakePackage()
        do_task = self.patch(yum, 'do_task')
        do_task.return_value = (baseurl, {finder.name: [package]})
        self.patch(finder, 'test_url').return_value = True
        url = finder._walk_source_repos(finder.name)
        self.assertEqual(baseurl + package.location, url)

    def test__walk_source_repos_different_version_miss(self):
        baseurl = self.factory.make_url()
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        package = self.FakePackage()
        do_task = self.patch(yum, 'do_task')
        do_task.return_value = (baseurl, {finder.name: [package]})
        self.patch(finder, 'test_url').return_value = False
        url = finder._walk_source_repos(finder.name)
        self.assertIsNone(url)

    def test__walk_binary_repos(self):
        src = [self.factory.make_url(), self.factory.make_url()]
        bin = [self.factory.make_url(), self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        n = self.factory.make_string()
        v = self.factory.make_semver()
        r = self.factory.randint(0, 100)
        srcrpm = self.make_package(n=n, v=v, r=r)
        package = self.FakePackage(vr=finder.version, sourcerpm=srcrpm)
        do_task = self.patch(yum, 'do_task')
        do_task.return_value = (None, {finder.name: [package]})
        name, version = finder._walk_binary_repos(finder.name)
        self.expectThat(name, Equals(n))
        self.expectThat(version, Equals(f"{v}-{r}"))

    def test__walk_binary_repos_no_sourcerpm(self):
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        package = self.FakePackage(vr=finder.version, sourcerpm='')
        do_task = self.patch(yum, 'do_task')
        do_task.return_value = (None, {finder.name: [package]})
        name, version = finder._walk_binary_repos(finder.name)
        self.assertIsNone(name)
        self.assertIsNone(version)

    def test__walk_binary_repos_different_name_multiple_versions(self):
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        package1 = self.FakePackage()
        package2 = self.FakePackage()
        do_task = self.patch(yum, 'do_task')
        do_task.return_value = (None, {finder.name: [package1, package2]})
        name, version = finder._walk_binary_repos(finder.name)
        self.assertIsNone(name)
        self.assertIsNone(version)

    def test__walk_binary_repos_different_name_different_version(self):
        src = [self.factory.make_url()]
        bin = [self.factory.make_url()]
        finder = self.make_finder(source_repos=src, binary_repos=bin)
        n = self.factory.make_string()
        v = self.factory.make_semver()
        r = self.factory.randint(0, 100)
        srcrpm = self.make_package(n=n, v=v, r=r)
        package = self.FakePackage(sourcerpm=srcrpm)
        do_task = self.patch(yum, 'do_task')
        do_task.return_value = (None, {finder.name: [package]})
        name, version = finder._walk_binary_repos(finder.name)
        self.expectThat(name, Equals(n))
        self.expectThat(version, Equals(f"{v}-{r}"))


class TestYumFinderClassHelpers(BaseYumTest):
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
        self.patch_head_with_response(requests.codes.ok)
        finder = self.make_finder()
        self.assertTrue(finder.test_url(url))

    def test__test_url_false(self):
        url = self.factory.make_url()
        self.patch_head_with_response(requests.codes.teapot)
        finder = self.make_finder()
        self.assertFalse(finder.test_url(url))

    def test__test_url_timeout(self):
        url = self.factory.make_url()
        self.patch(requests, 'head').side_effect = requests.exceptions.Timeout
        finder = self.make_finder()
        self.assertFalse(finder.test_url(url))


class TestYumFinderHelpers(BaseYumTest):
    def setUp(self):
        self.queue = mock.MagicMock()
        super().setUp()

    def test_get_repomd(self):
        # Mock up a successful repomd fetch
        url = self.factory.make_url()
        self.patch(requests, 'get')
        lxml = self.patch(repomd.defusedxml.lxml, 'parse')
        package = mock.MagicMock()
        lxml.return_value.getroot.return_value = [package]

        yum.get_repomd(self.queue, url)
        # Mocking out all the various and sundry Package properties would be
        # tedious, and we don't really care about anything past the package
        # name anyhow
        self.queue.put.assert_called_once_with(
            (url + "/", {package.findtext.return_value: [mock.ANY]})
        )

    def test_get_repomd_http_error(self):
        # Mock up a failure to fetch the repomd
        url = self.factory.make_url()
        load = self.patch(requests, 'get')
        load.side_effect = requests.exceptions.HTTPError()
        lxml = self.patch(repomd.defusedxml.lxml, 'parse')

        # Ensure that get_repomd won't fill the cache with garbage
        yum.get_repomd(self.queue, url)
        lxml.assert_not_called()
        self.queue.put.assert_called_once_with((load.side_effect,), timeout=30)

    def test_get_repomd_unserializable_http_error(self):
        # Ibid, but initializing the exception with a live file pointer will
        # make it refuse to serialize
        url = self.factory.make_url()
        fp = io.BufferedReader(io.StringIO())
        load = self.patch(requests, 'get')
        load.side_effect = requests.exceptions.RequestException(fp)
        lxml = self.patch(repomd.defusedxml.lxml, 'parse')

        # Ensure that we get a re-raised plain Exception
        yum.get_repomd(self.queue, url)
        lxml.assert_not_called()
        self.queue.put.assert_called_once_with((mock.ANY,), timeout=30)
        self.assertIn(
            're-raising as plain Exception', str(self.queue.put.call_args)
        )

    def test_do_task(self):
        # Mock up a process that does not exit upon return
        data = self.factory.make_string('response')
        queue = self.patch(yum, 'Queue')
        queue.return_value.get.return_value = data
        process = self.patch(yum, 'Process')
        process.return_value.is_alive.return_value = True

        # Ensure that the process gets shot in the head
        response = yum.do_task('a', 'b', 'c')
        self.assertEqual(data, response)
        process.return_value.terminate.assert_called_once_with()

    def test_do_task_empty_response(self):
        # Mock up a process that yields an "empty-but-successful" response
        queue = self.patch(yum, 'Queue')
        queue.return_value.get.return_value = []
        process = self.patch(yum, 'Process')
        process.return_value.is_alive.return_value = False

        # Ensure that the process gets shot in the head
        response = yum.do_task('d', 'e', 'f')
        self.assertEqual([], response)
        process.return_value.terminate.assert_not_called()

    def test_do_task_reraises_exceptions(self):
        # Actually run a job via do_task and ensure that the resulting
        # exception is intact
        data = self.factory.make_string('response')
        err = self.assertRaises(RuntimeError, yum.do_task, kaboom, data)
        self.assertEqual(data, str(err))

    def test_do_task_handles_spawn_errors_on_silly_platforms(self):
        # This simulates calling `process.start()` from the global scope on
        # platforms that do not support such things.  The default traceback
        # is not intrinsically helpful, so test that we kick back a more
        # useful error message.  See issue #31.
        process = self.patch(yum, 'Process')
        process.return_value.start.side_effect = RuntimeError(
            'Simulating a platform that is not using fork to start children'
        )
        err = self.assertRaises(SystemExit, yum.do_task, None)
        self.assertIn('FATAL: ', str(err))

    def test_do_task_leaves_other_spawn_errors_alone(self):
        # As per the above, other RuntimeError exceptions should pass through
        process = self.patch(yum, 'Process')
        process.return_value.start.side_effect = RuntimeError
        self.assertRaises(RuntimeError, yum.do_task, None)


# A simple subprocess function that throws a test exception.  Used by
# TestYumFinderHelpers.test_do_task_reraises_exceptions
def kaboom(queue, data):
    try:
        raise RuntimeError(data)
    except Exception as e:
        queue.put((e,))
    # This should never get called, but just in case...
    queue.put([])


class TestYumDiscoveredSource(base.TestCase):
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
