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
