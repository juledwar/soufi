# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import testtools

from soufi import finder
from soufi.finder import SourceType


class FunctionalFinderTests(testtools.TestCase):
    def setUp(self):
        self.skipTest("functional tests disabled for unit test runs")

    def test_find_photon_superseded_package(self):
        photon = finder.factory(
            'photon',
            name='curl-libs',
            version='7.75.0-2.ph4',
            s_type=SourceType.os,
        )
        url = 'https://packages.vmware.com/photon/4.0/photon_srpms_4.0_x86_64/curl-7.75.0-2.ph4.src.rpm'  # noqa: E501
        result = photon.find()
        self.assertEqual([url], result.urls)

    def test_find_centos_binary_from_source(self):
        # Test finding sources for binary packages with entirely different
        # names/versions.
        centos = finder.factory(
            'centos',
            name='device-mapper-libs',
            version='1.02.175-5.el8',
            s_type=SourceType.os,
        )
        url = 'https://vault.centos.org/centos/8.4.2105/BaseOS/Source/SPackages/lvm2-2.03.11-5.el8.src.rpm'  # noqa: E501
        result = centos.find()
        self.assertEqual([url], result.urls)

    def test_find_centos_binary_from_source_epoch(self):
        # Ibid, but with the epoch included with the version
        centos = finder.factory(
            'centos',
            name='device-mapper-libs',
            version='8:1.02.175-5.el8',
            s_type=SourceType.os,
        )
        url = 'https://vault.centos.org/centos/8.4.2105/BaseOS/Source/SPackages/lvm2-2.03.11-5.el8.src.rpm'  # noqa: E501
        result = centos.find()
        self.assertEqual([url], result.urls)

    def test_find_centos_binary_from_source_epoch_no_vault(self):
        # Ibid, but with a binary package not tracked in vault.  This test
        # will need updating if/when 7.9.2009 eventually gets vaulted.
        centos = finder.factory(
            'centos',
            name='bind-license',
            version='32:9.11.4-26.P2.el7',
            s_type=SourceType.os,
        )
        url = 'https://vault.centos.org/centos/7.9.2009/os/Source/SPackages/bind-9.11.4-26.P2.el7.src.rpm'  # noqa: E501
        result = centos.find()
        self.assertEqual([url], result.urls)

    def test_find_rhel_binary_from_source(self):
        # Test finding sources for binary packages with entirely different
        # names/versions.
        rhel = finder.factory(
            'rhel',
            name='vim-minimal',
            version='7.4.629-8.el7_9',
            s_type=SourceType.os,
        )
        url = 'https://cdn-ubi.redhat.com/content/public/ubi/dist/ubi/server/7/7Server/x86_64/source/SRPMS/Packages/v/vim-7.4.629-8.el7_9.src.rpm'  # noqa: E501
        result = rhel.find()
        self.assertEqual([url], result.urls)

    def test_find_rhel_binary_from_source_epoch(self):
        # Ibid, but with the epoch included with the version
        rhel = finder.factory(
            'rhel',
            name='vim-minimal',
            version='2:7.4.629-8.el7_9',
            s_type=SourceType.os,
        )
        url = 'https://cdn-ubi.redhat.com/content/public/ubi/dist/ubi/server/7/7Server/x86_64/source/SRPMS/Packages/v/vim-7.4.629-8.el7_9.src.rpm'  # noqa: E501
        result = rhel.find()
        self.assertEqual([url], result.urls)
