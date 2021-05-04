import pathlib
import shutil
import tempfile
from unittest import mock

import fixtures
import requests
import testtools
from testtools.matchers import FileContains

from sofi import exceptions
from sofi.finder import SourceType
from sofi.finders import npm
from sofi.testing import base


class TestNPMFinder(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return npm.NPMFinder(name, version, SourceType.npm)

    def make_response(self, data, code):
        fake_response = mock.MagicMock()
        fake_response.json.return_value = data
        fake_response.status_code = code
        return fake_response

    def test_get_source_url(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        data = dict(dist=dict(tarball=url))

        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        get.assert_called_once_with(
            f"https://registry.npmjs.org/{finder.name}/{finder.version}",
            timeout=30,
        )

    def test_get_source_info_raises_when_response_fails(self):
        get = self.patch(requests, 'get')
        get.return_value = self.make_response([], requests.codes.not_found)
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_find(self):
        url = self.factory.make_url()
        finder = self.make_finder()
        self.patch(finder, 'get_source_url').return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, npm.NPMDiscoveredSource)
        self.assertEqual([url], disc_source.urls)


class TestNPMDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return npm.NPMDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        nds = self.make_discovered_source(url)
        self.assertEqual(url, repr(nds))

    def test_make_archive(self):
        tmpdir = self.useFixture(fixtures.TempDir()).path

        # Make a fake tar file
        content = self.factory.make_bytes('content')
        _, fake_file = tempfile.mkstemp(dir=tmpdir)
        with open(fake_file, 'wb') as fake_file_fd:
            fake_file_fd.write(content)

        # Patch out download_file to return the fake file:
        nds = self.make_discovered_source()
        download_file = self.patch(nds, 'download_file')
        download_file.return_value = pathlib.Path(fake_file)

        # Call make_archive to fetch the fake file:
        _, tar_file_name = tempfile.mkstemp(dir=tmpdir)
        with nds.make_archive() as tarfile_fd:
            with open(tar_file_name, 'wb') as f:
                shutil.copyfileobj(tarfile_fd, f)

        # Test that the copied file contains the fake downloaded content.
        self.assertThat(tar_file_name, FileContains(content.decode()))
