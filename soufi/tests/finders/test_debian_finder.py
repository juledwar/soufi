# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import pathlib
import tarfile
import tempfile
from unittest import mock

import fixtures
import requests
import testtools
from testtools.matchers import Equals
from testtools.matchers._basic import SameMembers

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import debian
from soufi.testing import base


class TestDebianFinder(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return debian.DebianFinder(name, version, SourceType.os)

    def make_source_info(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string()
        if version is None:
            version = self.factory.make_string()
        return dict(name=name, version=version)

    def test_get_source_info(self):
        df = self.make_finder()
        source_version = self.factory.make_string()
        source_name = self.factory.make_string()

        data = dict(
            result=[
                {
                    'binary_version': self.factory.make_string(),
                    'source': self.factory.make_string(),
                    'version': self.factory.make_string(),
                    'name': self.factory.make_string(),
                },
                {
                    'binary_version': df.version,
                    'source': source_name,
                    'version': source_version,
                    'name': df.name,
                },
            ]
        )
        self.patch_get_with_response(requests.codes.ok, json=data)
        source_info = df.get_source_info()
        expected = dict(name=source_name, version=source_version)
        self.assertDictEqual(expected, source_info)

    def test_get_source_info_raises_when_response_fails(self):
        self.patch_get_with_response(requests.codes.not_found)
        df = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            df.get_source_info()

    def test_get_source_info_raises_when_cant_find_version(self):
        df = self.make_finder()
        data = dict(
            result=[
                {
                    'binary_version': self.factory.make_string(),
                    'source': self.factory.make_string(),
                    'version': self.factory.make_string(),
                    'name': self.factory.make_string(),
                },
            ]
        )
        self.patch_get_with_response(requests.codes.ok, json=data)
        with testtools.ExpectedException(exceptions.SourceNotFound):
            df.get_source_info()

    def test_get_hashes(self):
        df = self.make_finder()
        hashes = [self.factory.make_digest() for _ in range(4)]
        data = dict(result=[{'hash': hash} for hash in hashes])
        get = self.patch_get_with_response(requests.codes.ok, json=data)
        source_info = self.make_source_info()
        self.assertEqual(hashes, df.get_hashes(source_info))
        get.assert_called_once_with(
            f"{debian.SNAPSHOT_API}mr/package/"
            f"{source_info['name']}/{source_info['version']}/srcfiles",
            timeout=df.timeout,
        )

    def test_get_hashes_raises_for_requests_error(self):
        self.patch_get_with_response(requests.codes.bad_request)
        df = self.make_finder()
        source_info = self.make_source_info()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            df.get_hashes(source_info)

    def test_get_hashes_raises_for_response_error(self):
        df = self.make_finder()
        source_info = self.make_source_info()
        self.patch_get_with_response(requests.codes.ok, json=[])
        with testtools.ExpectedException(exceptions.SourceNotFound):
            df.get_hashes(source_info)

    def test_get_urls(self):
        df = self.make_finder()
        hashes = [self.factory.make_digest() for _ in range(2)]
        name = self.factory.make_string()
        data = dict(
            result=[dict(name=name), dict(name=self.factory.make_string())]
        )
        get = self.patch_get_with_response(requests.codes.ok, json=data)
        expected = [
            (name, f"{debian.SNAPSHOT_API}file/{hash}") for hash in hashes
        ]
        self.assertEqual(expected, df.get_urls(hashes))
        calls = [
            mock.call(
                f"{debian.SNAPSHOT_API}mr/file/{hash}/info",
                timeout=df.timeout,
            )
            for hash in hashes
        ]
        self.assertEqual(calls, get.call_args_list)

    def test_get_urls_raises_for_requests_error(self):
        df = self.make_finder()
        self.patch_get_with_response(requests.codes.bad_request)
        with testtools.ExpectedException(exceptions.DownloadError):
            df.get_urls(['foo'])

    def test_find(self):
        source_info = self.make_source_info()
        get_source_info = self.patch(debian.DebianFinder, 'get_source_info')
        get_source_info.return_value = source_info
        hashes = [self.factory.make_digest for _ in range(4)]
        urls = [self.factory.make_url for _ in range(4)]
        url_pairs = [(self.factory.make_string(), url) for url in urls]
        get_hashes = self.patch(debian.DebianFinder, 'get_hashes')
        get_hashes.return_value = hashes
        get_urls = self.patch(debian.DebianFinder, 'get_urls')
        get_urls.return_value = url_pairs
        df = self.make_finder()

        disc_source = df.find()

        get_source_info.assert_called_once()
        get_hashes.assert_called_once_with(source_info)
        get_urls.assert_called_once_with(hashes)
        names, urls = zip(*url_pairs)
        self.assertEqual(urls, disc_source.urls)
        self.assertEqual(names, disc_source.names)


class TestDebianDiscoveredSource(base.TestCase):
    def make_debian_discovered_source(self, url_count=3):
        urls = [self.factory.make_url() for _ in range(url_count)]
        url_pairs = [(self.factory.make_string(), url) for url in urls]
        return url_pairs, debian.DebianDiscoveredSource(url_pairs)

    def test_repr(self):
        url_pairs, dds = self.make_debian_discovered_source()
        expected = "\n".join([f"{name}: {url}" for name, url in url_pairs])
        self.assertEqual(expected, repr(dds))

    def test_populate_archive(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path

        # Make a file to put in the tar:
        content = self.factory.make_bytes('content')
        _, fake_file = tempfile.mkstemp(dir=tmpdir)
        with open(fake_file, 'wb') as fake_file_fd:
            fake_file_fd.write(content)

        # Patch out download_file to return the fake file:
        url_pairs, dds = self.make_debian_discovered_source(url_count=1)
        download_file = self.patch(dds, 'download_file')
        download_file.return_value = pathlib.Path(fake_file)

        # Make the tar file and populate it:
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir)
        with tarfile.open(name=tar_file_name, mode='w') as tar:
            dds.populate_archive(tmpdir, tar)

        # Test that the tar contains the file and the content.
        expected_file_name, _ = url_pairs[0]
        with tarfile.open(name=tar_file_name, mode='r') as tar:
            self.expectThat(tar.getnames(), SameMembers([expected_file_name]))
            self.expectThat(
                tar.extractfile(expected_file_name).read(), Equals(content)
            )
