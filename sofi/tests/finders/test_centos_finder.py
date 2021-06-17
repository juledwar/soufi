import urllib
from unittest import mock

import requests
import testtools

from sofi import exceptions
from sofi.finder import SourceType
from sofi.finders import centos
from sofi.testing import base


class BaseCentosTest(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return centos.CentosFinder(name, version, SourceType.os)

    def make_response(self, data, code):
        fake_response = mock.MagicMock()
        fake_response.content = data
        fake_response.status_code = code
        return fake_response

    def make_href(self, text):
        return f'<a href="{text}">{text}</a>'

    def make_td(self, href):
        return f'<td class="indexcolname">{href}</td>'

    def make_top_page_content(self, versions):
        links = [self.make_td(self.make_href(v)) for v in versions]
        return "\n".join(links)

    def make_index_page_content(self, name, version):
        # Makes something approximating the package index page from
        # vault.centos.org with our desired package at a random place.
        random_position = self.factory.randint(1, 8)
        rows = []
        for i in range(0, 10):
            if i == random_position:
                name_ = name
                version_ = version
            else:
                name_ = self.factory.make_string('name')
                version_ = self.factory.make_string('version')
            rows.append(
                self.make_td(self.make_href(f'{name_}-{version_}.src.rpm'))
            )
        return (
            b'<table id="indexlist">\n'
            + b'\n'.join(f'<tr>{row}</tr>'.encode('utf8') for row in rows)
            + b'</table>'
        )


class TestCentosFinder(BaseCentosTest):
    def setUp(self):
        super().setUp()
        # Make sure this doesn't interfere with fast lookup tests.
        self.patch(centos.CentosFinder, '_repo_lookup').return_value = None

    def test__get_dirs(self):
        finder = self.make_finder()
        versions = ['4.5', '7.0', '7.1', '8.0']
        versions_ = versions + ['ignored']
        data = self.make_top_page_content(versions_)
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        dirs = finder._get_dirs()
        self.assertEqual(versions, dirs)
        get.assert_called_once_with(
            "https://vault.centos.org/centos/", timeout=30
        )

    def test__get_path_pre_8_versions(self):
        finder = self.make_finder()
        data = self.make_index_page_content(finder.name, finder.version)
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        dir_ = self.factory.make_string('7.0') + '/'
        url = finder._get_path(dir_)

        base_url = (
            f'https://vault.centos.org/centos/{dir_}os/Source/SPackages/'
        )
        get.assert_called_once_with(base_url, timeout=30)
        self.assertEqual(
            f'{base_url}{finder.name}-{finder.version}.src.rpm', url
        )

    def test__get_path_8plus_versions(self):
        finder = self.make_finder()
        data = self.make_index_page_content(finder.name, finder.version)
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        dir_ = self.factory.make_string('8.0') + '/'
        url = finder._get_path(dir_)

        base_url = (
            f'https://vault.centos.org/centos/{dir_}BaseOS/Source/SPackages/'
        )
        get.assert_called_once_with(base_url, timeout=30)
        self.assertEqual(
            f'{base_url}{finder.name}-{finder.version}.src.rpm', url
        )

    def test__get_path_pre_6_2_versions(self):
        finder = self.make_finder()
        data = self.make_index_page_content(finder.name, finder.version)
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        for dir_ in ('6.1/', '6.0/', '5.0/'):
            url = finder._get_path(dir_)

            base_url = (
                f'https://vault.centos.org/centos/{dir_}os/Source/Packages/'
            )
            self.assertEqual(
                f'{base_url}{finder.name}-{finder.version}.src.rpm', url
            )

    def test__get_path_returns_None_if_not_found(self):
        finder = self.make_finder()
        data = self.make_index_page_content(
            self.factory.make_string(), self.factory.make_string()
        )
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        dir_ = self.factory.make_string('8.0') + '/'
        self.assertIsNone(finder._get_path(dir_))

    def test_find_raises_when_not_found(self):
        finder = self.make_finder()
        self.patch(finder, '_get_dirs').return_value = ['a']
        self.patch(finder, '_get_path').return_value = None
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.find()

    def test_find_raises_when_index_dir_missing(self):
        finder = self.make_finder()
        self.patch(finder, '_get_dirs').return_value = ['a']
        self.patch(finder, '_get_path').side_effect = exceptions.DownloadError
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.find()

    def test_find_raises_when_download_error(self):
        finder = self.make_finder()
        self.patch(requests, 'get').return_value = self.make_response(
            [], requests.codes.bad_request
        )
        with testtools.ExpectedException(exceptions.DownloadError):
            finder.find()

    def test_find(self):
        finder = self.make_finder()
        dir_ = self.factory.make_string('dir')
        url = self.factory.make_url()
        self.patch(finder, '_get_dirs').return_value = [dir_]
        self.patch(finder, '_get_path').return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, centos.CentosDiscoveredSource)
        self.assertEqual([url], disc_source.urls)

    def test_find_calls_get_repo_if_using_fallback_method(self):
        finder = self.make_finder(version='1.2.3.el8')
        self.patch(finder, '_get_dirs').return_value = []
        url = self.factory.make_url()
        self.patch(finder, '_repo_lookup').return_value = url
        self.assertEqual(url, finder._find().urls[0])


class TestCentosFinderRepoLookup(BaseCentosTest):
    def make_repo(self, evr, sourcerpm=None, location=None):
        repo = mock.MagicMock()
        findall = mock.MagicMock()
        repo.findall = findall
        package = mock.MagicMock()
        package.evr = evr
        package.sourcerpm = sourcerpm
        package.location = location
        findall.return_value = [package]
        return repo

    def test_returns_None_when_repo_load_fails(self):
        finder = self.make_finder()
        self.patch(finder, '_get_repo').return_value = None
        self.assertIsNone(finder._repo_lookup())

    def test_returns_None_when_package_not_found_in_repo(self):
        repo = self.make_repo(evr='')
        finder = self.make_finder()
        self.patch(finder, '_get_repo').return_value = repo
        self.assertIsNone(finder._repo_lookup())

    def test_returns_None_when_source_repo_load_fails(self):
        finder = self.make_finder()
        repo = self.make_repo(
            evr=finder.version,
            sourcerpm=f'{finder.name}-{finder.version}.src.rpm',
        )
        get_repo = self.patch(finder, '_get_repo')
        get_repo.side_effect = (repo, None)
        self.assertIsNone(finder._repo_lookup())
        self.assertEqual(2, len(get_repo.mock_calls))

    def test_returns_None_when_source_package_not_found_in_repo(self):
        finder = self.make_finder()
        repo = self.make_repo(
            evr=finder.version,
            sourcerpm=f'{finder.name}-{finder.version}.src.rpm',
        )
        src_repo = self.make_repo(evr='')
        get_repo = self.patch(finder, '_get_repo')
        get_repo.side_effect = (repo, src_repo)
        self.assertIsNone(finder._repo_lookup())
        self.assertEqual(2, len(get_repo.mock_calls))

    def test_returns_url_when_source_package_is_found(self):
        finder = self.make_finder()
        repo = self.make_repo(
            evr=finder.version,
            sourcerpm=f'{finder.name}-{finder.version}.src.rpm',
        )
        location = self.factory.make_string('location;')
        src_repo = self.make_repo(evr=finder.version, location=location)
        get_repo = self.patch(finder, '_get_repo')
        get_repo.side_effect = (repo, src_repo)
        self.assertEqual(
            f'{centos.VAULT}/8/BaseOS/Source/{location}', finder._repo_lookup()
        )

    def test__get_repo_returns_None_when_HTTPError(self):
        url = self.factory.make_url()
        load = self.patch(centos.repomd, 'load')
        load.side_effect = urllib.error.HTTPError(
            url, '404', 'foo', dict(), None
        )
        finder = self.make_finder()
        repo = finder._get_repo(url)
        self.assertIsNone(repo)

    def test__get_repo_returns_repo(self):
        load = self.patch(centos.repomd, 'load')
        load.return_value = mock.sentinel.REPO
        finder = self.make_finder()
        url = self.factory.make_url()
        repo = finder._get_repo(url)
        load.assert_called_once_with(url)
        self.assertEqual(repo, mock.sentinel.REPO)

    def test__get_repo_is_cached(self):
        load = self.patch(centos.repomd, 'load')
        url = self.factory.make_url()
        finder = self.make_finder()
        finder._get_repo(url)
        finder._get_repo(url)
        load.assert_called_once_with(url)


class TestCentosDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return centos.CentosDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        cds = self.make_discovered_source(url)
        self.assertEqual(url, repr(cds))

    def test_make_archive(self):
        cds = self.make_discovered_source()
        self.assertEqual(cds.make_archive, cds.remote_url_is_archive)
