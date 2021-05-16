from unittest import mock

import requests
import testtools

from sofi import exceptions
from sofi.finder import SourceType
from sofi.finders import python
from sofi.testing import base


class TestPythonFinder(base.TestCase):
    def make_finder(self, name=None, version=None, pyindex=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        kwargs = dict(name=name, version=version, s_type=SourceType.python)
        if pyindex is not None:
            kwargs['pyindex'] = pyindex
        return python.PythonFinder(**kwargs)

    def make_response(self, data, code):
        fake_response = mock.MagicMock()
        fake_response.json.return_value = data
        fake_response.status_code = code
        return fake_response

    def test_get_source_url(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        releases = {
            finder.version: [
                dict(packagetype='foobar', url='foobar'),
                dict(packagetype='sdist', url=url),
            ]
        }
        data = dict(releases=releases)

        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        get.assert_called_once_with(
            f"https://pypi.org/pypi/{finder.name}/{finder.version}/json",
            timeout=30,
        )

    def test_get_source_url_source_not_found(self):
        finder = self.make_finder()
        releases = {
            'badversion': [
                dict(packagetype='foobar', url='foobar'),
            ]
        }
        data = dict(releases=releases)

        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)

    def test_get_source_url_custom_index(self):
        index = self.factory.make_url()
        finder = self.make_finder(pyindex=index)
        url = self.factory.make_url()
        releases = {
            finder.version: [
                dict(packagetype='sdist', url=url),
            ]
        }
        data = dict(releases=releases)

        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        get.assert_called_once_with(
            f"{index}/{finder.name}/{finder.version}/json",
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
        self.assertIsInstance(disc_source, python.PythonDiscoveredSource)
        self.assertEqual([url], disc_source.urls)


class TestPythonDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return python.PythonDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        pds = self.make_discovered_source(url)
        self.assertEqual(url, repr(pds))

    def test_make_archive(self):
        pds = self.make_discovered_source()
        self.assertEqual(pds.make_archive, pds.remote_url_is_archive)
