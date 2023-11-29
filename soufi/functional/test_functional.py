# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import logging
import tempfile
from subprocess import run as run_cmd

import testtools

from soufi import finder
from soufi.finder import SourceType

# Setup a module-level cache dict so that it can be warmed up and re-used
# between tests
FUNCTEST_CACHE = dict()

# These tests will use the `memory_pickle` cache backend, which
# serializes the cache payload before storing it; this should surface
# any obvious problems with the other serializing cache backends
# without forcing them as a dependency.


class FunctionalFinderTests(testtools.TestCase):
    def setUp(self):
        # Enable dogpile.cache logging so we can eyeball the cache
        # population steps
        logging.basicConfig()
        logging.getLogger("dogpile.cache").setLevel(logging.DEBUG)
        super().setUp()


class FunctionalPhotonTests(FunctionalFinderTests):
    def test_find_superseded_package(self):
        photon = finder.factory(
            'photon',
            name='curl-libs',
            version='7.75.0-2.ph4',
            s_type=SourceType.os,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://packages.vmware.com/photon/4.0/photon_srpms_4.0_x86_64/curl-7.75.0-2.ph4.src.rpm'  # noqa: E501
        result = photon.find()
        self.assertEqual([url], result.urls)


class FunctionalCentOSTests(FunctionalFinderTests):
    def test_find_binary_from_source(self):
        # Test finding sources for binary packages with entirely different
        # names/versions.
        centos = finder.factory(
            'centos',
            name='device-mapper-libs',
            version='1.02.175-5.el8',
            s_type=SourceType.os,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://vault.centos.org/centos/8.4.2105/BaseOS/Source/SPackages/lvm2-2.03.11-5.el8.src.rpm'  # noqa: E501
        result = centos.find()
        self.assertEqual([url], result.urls)

    def test_find_binary_from_source_epoch(self):
        # Ibid, but with the epoch included with the version
        centos = finder.factory(
            'centos',
            name='device-mapper-libs',
            version='8:1.02.175-5.el8',
            s_type=SourceType.os,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://vault.centos.org/centos/8.4.2105/BaseOS/Source/SPackages/lvm2-2.03.11-5.el8.src.rpm'  # noqa: E501
        result = centos.find()
        self.assertEqual([url], result.urls)

    def test_find_binary_from_source_epoch_no_vault(self):
        # Ibid, but with a binary package not tracked in vault.  This test
        # will need updating if/when 7.9.2009 eventually gets vaulted.
        centos = finder.factory(
            'centos',
            name='bind-license',
            version='32:9.11.4-26.P2.el7',
            s_type=SourceType.os,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://vault.centos.org/centos/7.9.2009/os/Source/SPackages/bind-9.11.4-26.P2.el7.src.rpm'  # noqa: E501
        result = centos.find()
        self.assertEqual([url], result.urls)


class FunctionalRedhatTests(FunctionalFinderTests):
    def test_find_binary_from_source(self):
        # Test finding sources for binary packages with entirely different
        # names/versions.
        rhel = finder.factory(
            'rhel',
            name='vim-minimal',
            version='7.4.629-8.el7_9',
            s_type=SourceType.os,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://cdn-ubi.redhat.com/content/public/ubi/dist/ubi/server/7/7Server/x86_64/source/SRPMS/Packages/v/vim-7.4.629-8.el7_9.src.rpm'  # noqa: E501
        result = rhel.find()
        self.assertEqual([url], result.urls)

    def test_find_binary_from_source_epoch(self):
        # Ibid, but with the epoch included with the version
        rhel = finder.factory(
            'rhel',
            name='vim-minimal',
            version='2:7.4.629-8.el7_9',
            s_type=SourceType.os,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://cdn-ubi.redhat.com/content/public/ubi/dist/ubi/server/7/7Server/x86_64/source/SRPMS/Packages/v/vim-7.4.629-8.el7_9.src.rpm'  # noqa: E501
        result = rhel.find()
        self.assertEqual([url], result.urls)


class FunctionalAlpineTests(FunctionalFinderTests):
    def test_find_package(self):
        cmd = 'git clone --depth 1 --branch v3.13.5 git://git.alpinelinux.org/aports'.split()  # noqa: E501
        with tempfile.TemporaryDirectory('.aports') as aports_dir:
            output = run_cmd(
                cmd + [aports_dir], capture_output=True  # noqa: S603
            )
            msg = "\n".join(
                [output.stderr.decode('utf-8'), output.stdout.decode('utf-8')]
            )
            if 'fatal' in msg:
                self.fail(f"git clone failed: {cmd} {aports_dir} {msg}")
            alpine = finder.factory(
                'alpine',
                name='zlib',
                version='1.2.11-r3',
                aports_dir=aports_dir,
                s_type=SourceType.os,
                cache_backend='dogpile.cache.memory_pickle',
                cache_args=dict(cache_dict=FUNCTEST_CACHE),
            )
            url = 'https://zlib.net/zlib-1.2.11.tar.gz'
            result = alpine.find()
            self.assertEqual([url], result.urls)


class FunctionalUbuntuTests(FunctionalFinderTests):
    def test_find_package(self):
        ubuntu = finder.factory(
            'ubuntu',
            name='openssh-client',
            version='1:7.6p1-4ubuntu0.3',
            s_type=SourceType.os,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        urls = (
            'https://launchpad.net/ubuntu/+archive/primary/+sourcefiles/openssh/1:7.6p1-4ubuntu0.3/openssh_7.6p1-4ubuntu0.3.debian.tar.xz',  # noqa: E501
            'https://launchpad.net/ubuntu/+archive/primary/+sourcefiles/openssh/1:7.6p1-4ubuntu0.3/openssh_7.6p1-4ubuntu0.3.dsc',  # noqa: E501
            'https://launchpad.net/ubuntu/+archive/primary/+sourcefiles/openssh/1:7.6p1-4ubuntu0.3/openssh_7.6p1.orig.tar.gz',  # noqa: E501
            'https://launchpad.net/ubuntu/+archive/primary/+sourcefiles/openssh/1:7.6p1-4ubuntu0.3/openssh_7.6p1.orig.tar.gz.asc',  # noqa: E501
        )
        result = ubuntu.find()
        self.assertEqual(urls, result.urls)


class FunctionalDebianTests(FunctionalFinderTests):
    def test_find_package(self):
        debian = finder.factory(
            'debian',
            name='liblz4-1',
            version='1.8.3-1',
            s_type=SourceType.os,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        names = (
            'lz4_1.8.3.orig.tar.gz',
            'lz4_1.8.3-1.dsc',
            'lz4_1.8.3-1.debian.tar.xz',
        )
        urls = (
            'https://snapshot.debian.org/file/070867abcd93a7245b80ec6fc2ced27c6b8e3e0c',  # noqa: E501
            'https://snapshot.debian.org/file/c8bea6da056133de5da5ddedd0b1a65a19241f52',  # noqa: E501
            'https://snapshot.debian.org/file/85218375b0ba0ff7f989f85909d5560efdd2592d',  # noqa: E501
        )
        result = debian.find()
        self.assertEqual(names, result.names)
        self.assertEqual(urls, result.urls)


class FunctionalGemTests(FunctionalFinderTests):
    def test_find_package(self):
        gem = finder.factory(
            'gem',
            name='msgpack',
            version='1.3.1',
            s_type=SourceType.gem,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://rubygems.org/downloads/msgpack-1.3.1.gem'
        result = gem.find()
        self.assertEqual([url], result.urls)


class FunctionalGolangTests(FunctionalFinderTests):
    def test_find_package(self):
        golang = finder.factory(
            'go',
            name='github.com/beevik/ntp',
            version='v0.3.0',
            s_type=SourceType.go,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://proxy.golang.org/github.com/beevik/ntp/@v/v0.3.0.zip'
        result = golang.find()
        self.assertEqual([url], result.urls)


class FunctionalJavaTests(FunctionalFinderTests):
    def test_find_package(self):
        java = finder.factory(
            'java',
            name='log4j-core',
            version='2.9.1',  # vulnerable to log4shell
            s_type=SourceType.java,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://repo1.maven.org/maven2/org%2Fapache%2Flogging%2Flog4j%2Flog4j-core%2F2.9.1%2Flog4j-core-2.9.1-sources.jar'  # noqa: E501
        result = java.find()
        self.assertEqual([url], result.urls)


class FunctionalNPMTests(FunctionalFinderTests):
    def test_find_package(self):
        npm = finder.factory(
            'npm',
            name='react',
            version='16.14.0',
            s_type=SourceType.npm,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://registry.npmjs.org/react/-/react-16.14.0.tgz'
        result = npm.find()
        self.assertEqual([url], result.urls)


class FunctionalPythonTests(FunctionalFinderTests):
    def test_find_package(self):
        python = finder.factory(
            'python',
            name='SQLAlchemy',
            version='1.4.31',  # current version ;-)
            s_type=SourceType.python,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://files.pythonhosted.org/packages/0f/80/d8883f12689a55e333d221bb9a56c727e976f5a8e9dc862efeac9f40d296/SQLAlchemy-1.4.31.tar.gz'  # noqa: E501
        result = python.find()
        self.assertEqual([url], result.urls)


class FunctionalAlmaTests(FunctionalFinderTests):
    def test_find_binary_from_source(self):
        almalinux = finder.factory(
            'almalinux',
            name='glibc-common',
            version='2.34-60.el9_2.7',
            s_type=SourceType.os,
            cache_backend='dogpile.cache.memory_pickle',
            cache_args=dict(cache_dict=FUNCTEST_CACHE),
        )
        url = 'https://repo.almalinux.org/vault/9.2/BaseOS/Source/Packages/glibc-2.34-60.el9_2.7.src.rpm'  # noqa: E501
        result = almalinux.find()
        self.assertEqual([url], result.urls)
