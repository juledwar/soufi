from unittest import mock

import requests
import testtools

from sofi import exceptions
from sofi.finder import SourceType
from sofi.finders import debian
from sofi.testing import base


class TestDebianFinder(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return debian.DebianFinder(name, version, SourceType.os)

    def make_response(self, data, code):
        fake_response = mock.MagicMock()
        fake_response.json.return_value = data
        fake_response.status_code = code
        return fake_response

    def test_get_hashes(self):
        df = self.make_finder()
        hashes = [self.factory.make_digest for _ in range(4)]
        data = dict(result=[{'hash': hash} for hash in hashes])
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        self.assertEqual(hashes, df.get_hashes())
        get.assert_called_once_with(
            f"{debian.SNAPSHOT_API}mr/package/{df.name}/{df.version}/srcfiles",
            timeout=debian.API_TIMEOUT,
        )

    def test_get_hashes_raises_for_requests_error(self):
        get = self.patch(requests, 'get')
        get.return_value = self.make_response([], requests.codes.bad_request)
        df = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            df.get_hashes()

    def test_get_hashes_raises_for_response_error(self):
        df = self.make_finder()
        self.patch(requests, 'get').return_value = self.make_response(
            [], requests.codes.ok
        )
        with testtools.ExpectedException(exceptions.SourceNotFound):
            df.get_hashes()

    def test_get_urls(self):
        df = self.make_finder()
        hashes = [self.factory.make_digest() for _ in range(2)]
        name = self.factory.make_string()
        data = dict(
            result=[dict(name=name), dict(name=self.factory.make_string())]
        )
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        expected = [
            (name, f"{debian.SNAPSHOT_API}file/{hash}") for hash in hashes
        ]
        self.assertEqual(expected, df.get_urls(hashes))
        calls = [
            mock.call(
                f"{debian.SNAPSHOT_API}mr/file/{hash}/info",
                timeout=debian.API_TIMEOUT,
            )
            for hash in hashes
        ]
        self.assertEqual(calls, get.call_args_list)

    def test_get_urls_raises_for_requests_error(self):
        df = self.make_finder()
        self.patch(requests, 'get').return_value = self.make_response(
            [], requests.codes.bad_request
        )
        with testtools.ExpectedException(exceptions.DownloadError):
            df.get_urls(['foo'])

    def test_find(self):
        hashes = [self.factory.make_digest for _ in range(4)]
        urls = [self.factory.make_url for _ in range(4)]
        url_pairs = [(self.factory.make_string(), url) for url in urls]
        get_hashes = self.patch(debian.DebianFinder, 'get_hashes')
        get_hashes.return_value = hashes
        get_urls = self.patch(debian.DebianFinder, 'get_urls')
        get_urls.return_value = url_pairs
        df = self.make_finder()

        disc_source = df.find()

        get_hashes.assert_called_once()
        get_urls.assert_called_once_with(hashes)
        names, urls = zip(*url_pairs)
        self.assertEqual(urls, disc_source.urls)
        self.assertEqual(names, disc_source.names)


class TestDebianDiscoveredSource(base.TestCase):
    def test_repr(self):
        urls = [self.factory.make_url() for _ in range(4)]
        url_pairs = [(self.factory.make_string(), url) for url in urls]
        dds = debian.DebianDiscoveredSource(url_pairs)
        expected = "\n".join([f"{name}: {url}" for name, url in url_pairs])
        self.assertEqual(expected, repr(dds))
