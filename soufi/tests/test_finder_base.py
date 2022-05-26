# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import pathlib
import shutil
import tarfile
import tempfile
from io import BytesIO

import fixtures
import requests
import testtools
from testtools.matchers import DirExists, Equals, FileContains, Not
from testtools.matchers._basic import SameMembers

from soufi import exceptions
from soufi.finder import DiscoveredSource, SourceFinder, SourceType
from soufi.testing import base


class TestSourceFinderBase(base.TestCase):
    class TestFinder(SourceFinder):
        def distro(self):
            pass

        def _find(self):
            pass

    def test_stores_init_params(self):
        name = self.factory.make_string()
        version = self.factory.make_string()
        s_type = self.factory.pick_enum(SourceType)
        sf = self.TestFinder(name, version, s_type)
        self.expectThat(sf.name, Equals(name))
        self.expectThat(sf.version, Equals(version))
        self.expectThat(sf.s_type, Equals(s_type))

    def test_requires_distro_property(self):
        class TestFinder(SourceFinder):
            def find(self):
                pass

        name = self.factory.make_string()
        version = self.factory.make_string()
        s_type = self.factory.pick_enum(SourceType)
        with testtools.ExpectedException(TypeError) as e:
            TestFinder(name, version, s_type)
            self.assertIn('abstract methods distro', str(e))

    def test_requires_find_method(self):
        class TestFinder(SourceFinder):
            def distro(self):
                pass

        name = self.factory.make_string()
        version = self.factory.make_string()
        s_type = self.factory.pick_enum(SourceType)
        with testtools.ExpectedException(TypeError) as e:
            TestFinder(name, version, s_type)
            self.assertIn('abstract methods find', str(e))

    def test_find_overrides_constructor_values(self):
        name = self.factory.random_choice([None, self.factory.make_string()])
        version = self.factory.random_choice(
            [None, self.factory.make_string()]
        )
        s_type = self.factory.random_choice(
            [None, self.factory.pick_enum(SourceType)]
        )
        name2 = self.factory.make_string()
        version2 = self.factory.make_string()
        s_type2 = self.factory.pick_enum(SourceType)
        sf = self.TestFinder(name, version, s_type)
        sf.find(name2, version2, s_type2)

        self.expectThat(sf.name, Equals(name2))
        self.expectThat(sf.version, Equals(version2))
        self.expectThat(sf.s_type, Equals(s_type2))

    def test_error_if_missing_find_value(self):
        for values in [
            (None, self.factory.make_string(), self.factory.make_string()),
            (self.factory.make_string(), None, self.factory.make_string()),
            (self.factory.make_string(), self.factory.make_string(), None),
        ]:
            sf = self.TestFinder(*values)
            e = self.assertRaises(ValueError, sf.find)
            self.assertEqual(
                "All of name, version and s_type must have a value", str(e)
            )


class TestDiscoveredSourceBase(base.TestCase):
    class TestDiscoveredSource(DiscoveredSource):
        def __init__(self, filename=None, content=None, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fake_content = content
            self.fake_filename = filename

        def populate_archive(self, temp_dir, tar):
            self.temp_dir = temp_dir
            _, fake_file = tempfile.mkstemp(dir=temp_dir)
            with open(fake_file, 'wb') as fake_file_fd:
                fake_file_fd.write(self.fake_content)
            tar.add(fake_file, arcname=self.fake_filename)

    def test_make_archive_yields_fileobj_to_tar(self):
        filename = self.factory.make_string('filename')
        content = self.factory.make_bytes('content')
        tds = self.TestDiscoveredSource(filename, content, urls=[])

        with tds.make_archive() as fd:
            with tarfile.open(mode='r', fileobj=fd) as tar:
                self.expectThat(tar.getnames(), SameMembers([filename]))
                self.expectThat(
                    tar.extractfile(filename).read(), Equals(content)
                )

    def test_make_archive_cleans_up_temp_dir_after_exit(self):
        filename = self.factory.make_string('filename')
        content = self.factory.make_bytes('content')
        tds = self.TestDiscoveredSource(filename, content, urls=[])
        with tds.make_archive() as _:
            self.assertThat(tds.temp_dir, DirExists())
        self.assertThat(tds.temp_dir, Not(DirExists()))

    def test_download_file_streams_file_to_target(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path
        target = self.factory.make_string('filename')
        url = self.factory.make_url()
        content = self.factory.make_bytes('content')
        response = requests.Response()
        response.status_code = requests.codes.ok
        response.raw = BytesIO(content)
        get = self.patch(requests, 'get')
        get.return_value = response

        f = self.factory.make_string('filename')
        c = self.factory.make_bytes('content')
        tds = self.TestDiscoveredSource(f, c, urls=[])
        returned_path = tds.download_file(tmpdir, target, url)

        expected_path = pathlib.Path(tmpdir) / target
        get.assert_called_once_with(url, stream=True, timeout=30)
        self.assertThat(expected_path, Equals(returned_path))
        # Cannot use matchers.FileContains because it returns decoded
        # strings...damn.
        with open(returned_path, 'rb') as fd:
            self.assertThat(fd.read(), Equals(content))

    def test_download_file_raises_on_http_errors(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path
        target = self.factory.make_string('filename')
        url = self.factory.make_url()
        response = requests.Response()
        response.status_code = requests.codes.not_found
        response.raw = BytesIO(b'')
        get = self.patch(requests, 'get')
        get.return_value = response

        tds = self.TestDiscoveredSource(urls=[])
        exc = self.assertRaises(
            exceptions.DownloadError,
            tds.download_file,
            tmpdir,
            target,
            url,
        )
        self.assertEqual(response.status_code, exc.status_code)

        expected_path = pathlib.Path(tmpdir) / target
        get.assert_called_once_with(url, stream=True, timeout=30)
        self.assertFalse(expected_path.exists())

    def test_filter_tarinfo(self):
        tarinfo = tarfile.TarInfo()
        tarinfo.uid = tarinfo.gid = self.factory.randint(0, 100)
        tarinfo.uname = tarinfo.gname = self.factory.make_string()
        filename = self.factory.make_string('filename')
        content = self.factory.make_bytes('content')
        tds = self.TestDiscoveredSource(filename, content, urls=[])
        tarinfo = tds.reset_tarinfo(tarinfo)
        self.expectThat(tarinfo.uid, Equals(0))
        self.expectThat(tarinfo.gid, Equals(0))
        self.expectThat(tarinfo.uname, Equals('root'))
        self.expectThat(tarinfo.gname, Equals('root'))

    def test_remote_url_is_archive(self):
        class URLDiscoveredSource(DiscoveredSource):
            make_archive = DiscoveredSource.remote_url_is_archive
            populate_archive = lambda: None  # noqa: E731

        tmpdir = self.useFixture(fixtures.TempDir()).path

        # Make a fake tar file
        content = self.factory.make_bytes('content')
        _, fake_file = tempfile.mkstemp(dir=tmpdir)
        with open(fake_file, 'wb') as fake_file_fd:
            fake_file_fd.write(content)

        # Patch out download_file to return the fake file:
        ds = URLDiscoveredSource(urls=[self.factory.make_url()])
        download_file = self.patch(ds, 'download_file')
        download_file.return_value = pathlib.Path(fake_file)

        # Call make_archive to fetch the fake file:
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir)
        with ds.make_archive() as tarfile_fd:
            with open(tar_file_name, 'wb') as f:
                shutil.copyfileobj(tarfile_fd, f)

        # Test that the copied file contains the fake downloaded content.
        self.assertThat(tar_file_name, FileContains(content.decode()))
