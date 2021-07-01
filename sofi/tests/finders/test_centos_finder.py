import urllib
from unittest import mock

import requests
import testtools
from testtools.matchers._basic import SameMembers

from sofi import exceptions
from sofi.finder import SourceType
from sofi.finders import centos
from sofi.testing import base


class BaseCentosTest(base.TestCase):
    def make_finder(self, name=None, version=None, **kwargs):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return centos.CentosFinder(name, version, SourceType.os, **kwargs)

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

    def test_source_dirs_setup_default(self):
        finder = self.make_finder()
        self.assertEqual(finder.source_dirs, finder.default_source_dirs)

    def test_source_dirs_setup_optimal(self):
        finder = self.make_finder(optimal_repos=True)
        self.assertEqual(finder.source_dirs, finder.optimal_source_dirs)

    def test_source_dirs_setup_custom(self):
        repos = ['foo', 'bar', 'baz']
        finder = self.make_finder(repos=repos)
        expected_repos = [f"{r}/" for r in repos]
        self.assertEqual(finder.source_dirs, expected_repos)

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

    def test__get_path(self):
        finder = self.make_finder()
        data = self.make_index_page_content(finder.name, finder.version)
        ref = finder._get_path(data)
        self.assertEqual(f'{finder.name}-{finder.version}.src.rpm', ref)

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
        url = self.factory.make_url()
        self.patch(finder, '_get_dirs').return_value = ['a']
        self.patch(finder, '_get_source_dirs_content').return_value = [
            (url, 'data')
        ]
        self.patch(finder, '_get_path').return_value = None
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
        ref = self.factory.make_string()
        self.patch(finder, '_get_dirs').return_value = [dir_]
        self.patch(finder, '_get_source_dirs_content').return_value = [
            (url, 'data')
        ]
        self.patch(finder, '_get_path').return_value = ref

        disc_source = finder.find()
        self.assertIsInstance(disc_source, centos.CentosDiscoveredSource)
        self.assertEqual([f"{url}/{ref}"], disc_source.urls)

    def test_find_calls_get_repo_if_using_fallback_method(self):
        finder = self.make_finder(version='1.2.3.el8')
        self.patch(finder, '_get_dirs').return_value = []
        url = self.factory.make_url()
        self.patch(finder, '_repo_lookup').return_value = url
        self.assertEqual(url, finder._find().urls[0])


class TestGetDirsScenarios(BaseCentosTest):

    scenarios = [
        ('6.0', dict(version='6.0', append='.el6')),
        ('7.0', dict(version='7.0', append='.el7')),
        ('8.0', dict(version='8.0', append='.el8')),
    ]

    def test__get_dirs_ignores_dirs_based_on_package_version(self):
        # If the version has got a string like 'el7' in it, then only look
        # in dirs starting with a 7. Same for el8, etc.
        finder = self.make_finder()
        versions = ['6.0', '7.0', '8.0']
        data = self.make_top_page_content(versions)
        get = self.patch(requests, 'get')
        get.return_value = self.make_response(data, requests.codes.ok)
        finder.version += self.append
        dirs = finder._get_dirs()
        self.assertEqual([self.version], dirs)


class TestGetSourceDirsContentScenarios(BaseCentosTest):

    scenarios = [
        ('post_v8', dict(release='8.0', packages_dir='SPackages')),
        ('pre_v8', dict(release='7.1', packages_dir='SPackages')),
        ('6.1', dict(release='6.1', packages_dir='Packages')),
        ('6.0', dict(release='6.0', packages_dir='Packages')),
        ('pre_6.0', dict(release='5.0', packages_dir='Packages')),
    ]

    def test_get_source_dirs_content(self):
        finder = self.make_finder()
        # Ensure irrelevant repo dirs are ignored with the 'bogus' one.
        repos = ('os/', 'extras/', 'BaseOS/', 'bogus/')
        expected_repos = ('os/', 'BaseOS/')
        top_data = self.make_top_page_content(repos)
        data = self.make_index_page_content(finder.name, finder.version)
        get = self.patch(requests, 'get')
        # Set up responses for the top index, and the packages indexes for each
        # item in repos. The 'extras' repo is a broken one which will get a
        # 404.
        get.side_effect = (
            self.make_response(top_data, requests.codes.ok),
            self.make_response(data, requests.codes.ok),
            self.make_response(b'', requests.codes.not_found),
            self.make_response(data, requests.codes.ok),
        )
        dir_ = self.release + '/'
        # Consume iterator.
        yielded = [_ for _ in finder._get_source_dirs_content(dir_)]

        # We expect it to spit out pairs of (url, data), where each url is the
        # path to the eventual packages_dir that contains the package, and data
        # is the content of the page at that location.
        expected = [
            (
                f"{centos.VAULT}{dir_}{expected_os_dir}Source/"
                f"{self.packages_dir}",
                data,
            )
            # Ensure only returned source dirs are considered.
            for expected_os_dir in expected_repos
        ]
        self.assertThat(yielded, SameMembers(expected))


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
        num_source_dirs = len(finder.source_dirs)
        get_repo.side_effect = (repo, src_repo) * num_source_dirs
        self.assertIsNone(finder._repo_lookup())
        self.assertEqual(2 * num_source_dirs, len(get_repo.mock_calls))

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
        # Will match the first source_dirs entry as we made the fake
        # repo match right away.
        self.assertEqual(
            f'{centos.VAULT}8/{finder.source_dirs[0]}' f'Source/{location}',
            finder._repo_lookup(),
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
