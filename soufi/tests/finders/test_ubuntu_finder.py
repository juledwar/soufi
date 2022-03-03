# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import pathlib
import tarfile
import tempfile
from unittest import mock

import fixtures
import testtools
from testtools.matchers import Equals
from testtools.matchers._basic import SameMembers

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import ubuntu
from soufi.testing import base


class TestUbuntuFinder(base.TestCase):
    def tearDown(self):
        super().tearDown()
        ubuntu.UbuntuFinder.get_archive.cache_clear()

    def make_finder(self, name=None, version=None, **kwargs):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return ubuntu.UbuntuFinder(name, version, SourceType.os, **kwargs)

    def test_init_auths_to_Launchpad_only_once(self):
        login = self.patch(ubuntu.Launchpad, 'login_anonymously')
        self.make_finder()
        self.make_finder()
        login.assert_called_once_with(
            "soufi", "production", mock.ANY, version="devel", timeout=30
        )

    def test_get_archive(self):
        lp = mock.MagicMock()
        distro = mock.MagicMock()
        lp.distributions.__getitem__.return_value = distro
        archive = mock.MagicMock()
        distro.main_archive = archive
        login = self.patch(ubuntu.Launchpad, 'login_anonymously')
        login.return_value = lp
        uf = self.make_finder()
        self.assertEqual(archive, uf.get_archive())

    def test_get_build(self):
        archive = mock.MagicMock()
        self.patch(ubuntu.UbuntuFinder, 'get_archive').return_value = archive
        getPublishedBinaries = mock.MagicMock()
        archive.getPublishedBinaries = getPublishedBinaries
        binary = mock.MagicMock()
        binary.build = mock.sentinel.BUILD
        getPublishedBinaries.return_value = [binary, mock.MagicMock()]
        uf = self.make_finder()
        build = uf.get_build()
        archive.getPublishedBinaries.assert_called_once_with(
            exact_match=True, binary_name=uf.name, version=uf.version
        )
        self.assertEqual(build, mock.sentinel.BUILD)

    def test_get_build_raises_for_no_build(self):
        archive = mock.MagicMock()
        self.patch(ubuntu.UbuntuFinder, 'get_archive').return_value = archive
        getPublishedBinaries = mock.MagicMock()
        archive.getPublishedBinaries = getPublishedBinaries
        getPublishedBinaries.return_value = []
        uf = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            uf.get_build()

    def test_get_source_from_build(self):
        archive = mock.MagicMock()
        self.patch(ubuntu.UbuntuFinder, 'get_archive').return_value = archive
        getPublishedSources = mock.MagicMock()
        archive.getPublishedSources = getPublishedSources
        source = mock.sentinel.SOURCE
        getPublishedSources.return_value = [source, mock.MagicMock()]
        build = mock.MagicMock()
        build.source_package_name = self.factory.make_string()
        build.source_package_version = self.factory.make_string()
        uf = self.make_finder()
        result = uf.get_source_from_build(build)
        getPublishedSources.assert_called_once_with(
            exact_match=True,
            source_name=build.source_package_name,
            version=build.source_package_version,
        )
        self.assertEqual(source, result)

    def test_find_returns_discovered_source(self):
        self.patch(ubuntu.UbuntuFinder, 'get_archive')
        self.patch(ubuntu.UbuntuFinder, 'get_build')
        source = mock.MagicMock()
        sourceFileUrls = mock.MagicMock()
        sourceFileUrls.return_value = [
            self.factory.make_url(),
            self.factory.make_url(),
        ]
        source.sourceFileUrls = sourceFileUrls
        self.patch(
            ubuntu.UbuntuFinder, 'get_source_from_build'
        ).return_value = source
        uf = self.make_finder()
        disc_source = uf.find()
        self.assertIsInstance(disc_source, ubuntu.UbuntuDiscoveredSource)
        self.assertThat(
            disc_source.urls, SameMembers(sourceFileUrls.return_value)
        )


class TestUbuntuDiscoveredSource(base.TestCase):
    def test_repr(self):
        urls = [self.factory.make_url() for _ in range(4)]
        uds = ubuntu.UbuntuDiscoveredSource(urls)
        expected = "\n".join(urls)
        self.assertEqual(expected, repr(uds))

    def test_populate_archive(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path

        # Make a file to put in the tar:
        content = self.factory.make_bytes('content')
        _, fake_file = tempfile.mkstemp(dir=tmpdir)
        with open(fake_file, 'wb') as fake_file_fd:
            fake_file_fd.write(content)

        # Patch out download_file to return the fake file:
        url = self.factory.make_url()
        uds = ubuntu.UbuntuDiscoveredSource([url])
        download_file = self.patch(uds, 'download_file')
        download_file.return_value = pathlib.Path(fake_file)

        # Make the tar file and populate it:
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir)
        with tarfile.open(name=tar_file_name, mode='w') as tar:
            uds.populate_archive(tmpdir, tar)

        # Test that the tar contains the file and the content.
        expected_file_name = url.rsplit('/', 1)[-1]
        with tarfile.open(name=tar_file_name, mode='r') as tar:
            self.expectThat(tar.getnames(), SameMembers([expected_file_name]))
            self.expectThat(
                tar.extractfile(expected_file_name).read(), Equals(content)
            )
