from unittest import mock

import testtools
from testtools.matchers._basic import SameMembers

from sofi import exceptions
from sofi.finder import SourceType
from sofi.finders import ubuntu
from sofi.testing import base


class TestUbuntuFinder(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        return ubuntu.UbuntuFinder(name, version, SourceType.os)

    def test_init_auths_to_Launchpad_only_once(self):
        login = self.patch(ubuntu.Launchpad, 'login_anonymously')
        self.make_finder()
        self.make_finder()
        login.assert_called_once_with(
            "sofi", "production", mock.ANY, version="devel"
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
