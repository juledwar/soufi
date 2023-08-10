# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import os
import tarfile
import tempfile
import urllib
import warnings
from hashlib import sha512
from io import BytesIO
from pathlib import Path

import fixtures
import testtools
from testtools.matchers import Equals
from testtools.matchers._basic import SameMembers

from soufi import exceptions, testing
from soufi.finder import SourceType
from soufi.finders import alpine
from soufi.testing import base


class TestAlpineFinder(base.TestCase):
    # This test suite uses static test data. This is against my normal
    # policies of using a factory where possible, but creating an aports
    # repo is just too complex. The data on disk contains a handful of
    # packages copied directly from the 3.14-stable release, which cover all
    # the tests that need to happen.

    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        self.aports_dir = Path(testing.__path__[0]) / 'data' / 'aports'
        kwargs = dict(
            name=name,
            version=version,
            s_type=SourceType.os,
            aports_dir=self.aports_dir,
        )
        return alpine.AlpineFinder(**kwargs)

    def test_raises_when_package_not_found(self):
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.find()

    def test_raises_when_package_exists_but_no_version_match(self):
        finder = self.make_finder('dbus', '9999-0')
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.find()

    def test_finds_simple_package(self):
        # The simple case where a package name matches a directory in the
        # aports repo.
        finder = self.make_finder('dbus', '1.12.20-2')
        source = finder.find()
        file_prefix = f"file://{self.aports_dir}/main/dbus"
        expected = [
            "https://dbus.freedesktop.org/releases/dbus/dbus-1.12.20.tar.gz",
            f"{file_prefix}/0001-_dbus_generate_random_bytes-use-getrandom-2.patch",  # noqa: E501
            f"{file_prefix}/avoid-opendir-between-fork-exec.patch",
            f"{file_prefix}/dbus.initd",
        ]
        self.assertThat(source.urls, SameMembers(expected))

    def test_finds_simple_package_with_r_prefix_on_release(self):
        # When passing versions as version-rN, ensure it still matches.
        finder = self.make_finder('dbus', '1.12.20-r2')
        source = finder.find()
        file_prefix = f"file://{self.aports_dir}/main/dbus"
        expected = [
            "https://dbus.freedesktop.org/releases/dbus/dbus-1.12.20.tar.gz",
            f"{file_prefix}/0001-_dbus_generate_random_bytes-use-getrandom-2.patch",  # noqa: E501
            f"{file_prefix}/avoid-opendir-between-fork-exec.patch",
            f"{file_prefix}/dbus.initd",
        ]
        self.assertThat(source.urls, SameMembers(expected))

    def test_finds_subpackage(self):
        # Complex case where the target to find is a subpackage of a source.
        finder = self.make_finder('dbus-dev', '1.12.20-2')
        source = finder.find()
        file_prefix = f"file://{self.aports_dir}/main/dbus"
        expected = [
            "https://dbus.freedesktop.org/releases/dbus/dbus-1.12.20.tar.gz",
            f"{file_prefix}/0001-_dbus_generate_random_bytes-use-getrandom-2.patch",  # noqa: E501
            f"{file_prefix}/avoid-opendir-between-fork-exec.patch",
            f"{file_prefix}/dbus.initd",
        ]
        self.assertThat(source.urls, SameMembers(expected))

    def test_finds_subpackage_in_provides(self):
        # Similar to above, except the subpackage is in the "provides".
        finder = self.make_finder('xproto', '2021.4-0')
        source = finder.find()
        expected = [
            "https://xorg.freedesktop.org/archive/individual/proto/xorgproto-2021.4.tar.bz2"  # noqa: E501
        ]
        self.assertThat(source.urls, SameMembers(expected))

    def test_finds_subpackage_with_function(self):
        # Ensure we can still match package:_function in the subpackages
        finder = self.make_finder('libcrypto1.1', '1.1.1k-0')
        source = finder.find()
        file_prefix = f"file://{self.aports_dir}/main/openssl"
        expected = [
            'https://www.openssl.org/source/openssl-1.1.1k.tar.gz',
            f'{file_prefix}/man-section.patch',
            f'{file_prefix}/ppc64.patch',
        ]
        self.assertThat(source.urls, SameMembers(expected))

    def test_ignores_virtual_packages(self):
        # The lua5.2 5.2.4-7 package has a provides="lua" line, with no
        # version.  Check that this package is ignored.
        finder = self.make_finder(name="lua", version="5.2.4-7")
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.find()

    def test_catches_badly_formed_APKBUILD(self):
        name = self.factory.make_string()
        tmpdir = self.useFixture(fixtures.TempDir()).path
        apkbuild_dir = Path(tmpdir) / 'main' / name
        os.makedirs(apkbuild_dir)
        content = self.factory.make_bytes('content')
        with open(apkbuild_dir / 'APKBUILD', 'wb') as fake_file_fd:
            fake_file_fd.write(content)

        finder = alpine.AlpineFinder(
            name=name, version='bar', aports_dir=tmpdir, s_type=SourceType.os
        )
        with testtools.ExpectedException(exceptions.DownloadError):
            finder.find()

    def test_processes_ftp_sources(self):
        # The gdbm package has a single ftp source in it.
        finder = self.make_finder('gdbm', '1.13-1')
        source = finder.find()
        self.assertThat(
            source.urls,
            SameMembers(['ftp://ftp.nluug.nl/pub/gnu/gdbm/gdbm-1.13.tar.gz']),
        )


class TestAlpineDiscoveredSource(base.TestCase):
    def make_discovered_source(self, urls=None):
        if urls is None:
            urls = [self.factory.make_url()]
        return alpine.AlpineDiscoveredSource(urls)

    def make_file_with_content(self, target_dir, content: bytes = None):
        if content is None:
            content = self.factory.make_bytes('content')
        _, fake_file = tempfile.mkstemp(dir=target_dir)
        with open(fake_file, 'wb') as fake_file_fd:
            fake_file_fd.write(content)
        return fake_file

    def assert_tarfile_name_and_content(
        self, tar_file_name, expected_file_name, content
    ):
        # Test that the tar contains the file and the content.
        with tarfile.open(name=tar_file_name, mode='r') as tar:
            self.expectThat(tar.getnames(), SameMembers([expected_file_name]))
            self.expectThat(
                tar.extractfile(expected_file_name).read(), Equals(content)
            )

    def test_repr(self):
        urls = [self.factory.make_url() for _ in range(3)]
        ads = alpine.AlpineDiscoveredSource(urls)
        expected = "\n".join(urls)
        self.assertEqual(expected, repr(ads))

    def test_populate_archive(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path
        content = self.factory.make_bytes('content')
        fake_file = self.make_file_with_content(tmpdir, content)

        # Patch out download_file to return the fake file:
        url = self.factory.make_url()
        sha512sum = {os.path.basename(url): sha512(content).hexdigest()}
        ads = alpine.AlpineDiscoveredSource([url], sha512sums=sha512sum)
        download_file = self.patch(ads, 'download_file')
        download_file.return_value = Path(fake_file)

        # Make the tar file and populate it:
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir)
        with tarfile.open(name=tar_file_name, mode='w') as tar:
            ads.populate_archive(tmpdir, tar)

        # Test that the tar contains the file and the content.
        expected_file_name = url.rsplit('/', 1)[-1]
        self.assert_tarfile_name_and_content(
            tar_file_name, expected_file_name, content
        )

    def test_populate_archive_warns_on_missing_checksum(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path
        content = self.factory.make_bytes('content')
        fake_file = self.make_file_with_content(tmpdir, content)
        warn = self.patch(warnings, 'warn')

        # Patch out download_file to return the fake file:
        url = self.factory.make_url()
        pathname = os.path.basename(url)
        ads = alpine.AlpineDiscoveredSource([url])
        download_file = self.patch(ads, 'download_file')
        download_file.return_value = Path(fake_file)

        # Make the tar file and populate it:
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir)
        with tarfile.open(name=tar_file_name, mode='w') as tar:
            ads.populate_archive(tmpdir, tar)

        # Test that the tar contains the file and the content.
        expected_file_name = url.rsplit('/', 1)[-1]
        self.assert_tarfile_name_and_content(
            tar_file_name, expected_file_name, content
        )
        warn.assert_called_once_with(
            f'No checksum for source file {pathname}, cannot verify',
            stacklevel=1,
        )

    def test_populate_archive_raises_on_mismatched_checksum(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path
        content = self.factory.make_bytes('content')
        fake_file = self.make_file_with_content(tmpdir, content)

        # Patch out download_file to return the fake file:
        url = self.factory.make_url()
        pathname = os.path.basename(url)
        sha512sum = {pathname: 'invalid'}
        ads = alpine.AlpineDiscoveredSource([url], sha512sums=sha512sum)
        download_file = self.patch(ads, 'download_file')
        download_file.return_value = Path(fake_file)

        # Make the tar file and populate it:
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir)
        with tarfile.open(name=tar_file_name, mode='w') as tar:
            exc = self.assertRaises(
                exceptions.DownloadError, ads.populate_archive, tmpdir, tar
            )
            self.assertIsNone(exc.status_code)

    def test_populate_archive_with_file_scheme(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path
        content = self.factory.make_bytes('content')
        fake_file = self.make_file_with_content(tmpdir, content)

        url = "file://" + str(fake_file)
        sha512sum = {os.path.basename(url): sha512(content).hexdigest()}
        ads = alpine.AlpineDiscoveredSource([url], sha512sums=sha512sum)
        download_file = self.patch(ads, 'download_file')
        download_file.return_value = Path(fake_file)

        # Make the tar file and populate it:
        tmpdir2 = self.useFixture(fixtures.TempDir()).path
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir2)
        with tarfile.open(name=tar_file_name, mode='w') as tar:
            ads.populate_archive(tmpdir2, tar)

        # Test that the tar contains the file and the content.
        expected_file_name = url.rsplit('/', 1)[-1]
        self.assert_tarfile_name_and_content(
            tar_file_name, expected_file_name, content
        )

    def test_populate_archive_with_custom_filename_prefix(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path
        content = self.factory.make_bytes('content')
        fake_file = self.make_file_with_content(tmpdir, content)

        # Patch out download_file to return the fake file:
        custom_name = self.factory.make_string("name")
        url = f"{custom_name}::{self.factory.make_url()}"
        sha512sum = {custom_name: sha512(content).hexdigest()}
        ads = alpine.AlpineDiscoveredSource([url], sha512sums=sha512sum)
        download_file = self.patch(ads, 'download_file')
        download_file.return_value = Path(fake_file)

        # Make the tar file and populate it:
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir)
        with tarfile.open(name=tar_file_name, mode='w') as tar:
            ads.populate_archive(tmpdir, tar)

        # Test that the tar contains the file and the content.
        self.assert_tarfile_name_and_content(
            tar_file_name, custom_name, content
        )

    def test_download_ftp_file(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path
        url = self.factory.make_url(scheme='ftp')
        content = self.factory.make_bytes('content')
        response = BytesIO(content)
        urlopen = self.patch(urllib.request, 'urlopen')
        urlopen.return_value = response
        sha512sum = {os.path.basename(url): sha512(content).hexdigest()}

        ads = alpine.AlpineDiscoveredSource(urls=[url], sha512sums=sha512sum)
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir)
        with tarfile.open(name=tar_file_name, mode='w') as tar:
            ads.populate_archive(tmpdir, tar)

        # Test that the tar contains the file and the content.
        expected_file_name = url.rsplit('/', 1)[-1]
        self.assert_tarfile_name_and_content(
            tar_file_name, expected_file_name, content
        )
