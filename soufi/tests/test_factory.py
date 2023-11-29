# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from unittest.mock import MagicMock

from soufi.finder import SourceType, factory
from soufi.finders import ubuntu
from soufi.testing import base


class TestFinderFactory(base.TestCase):
    def test_factory_loads_finder_classes(self):
        # Until the finder path is configurable, just check that the
        # Ubuntu finder is present.
        self.assertEqual(
            factory._finders[ubuntu.UbuntuFinder.distro], ubuntu.UbuntuFinder
        )

    def test_factory_passes_args_when_calling(self):
        name = self.factory.make_string()
        version = self.factory.make_string()
        finder_mock = MagicMock()
        factory._finders[ubuntu.UbuntuFinder.distro] = finder_mock
        factory(ubuntu.UbuntuFinder.distro, name, version, SourceType.os)
        finder_mock.assert_called_once_with(name, version, SourceType.os)

    def test_supported_types(self):
        expected = [
            'almalinux',
            'alpine',
            'centos',
            'debian',
            'gem',
            'go',
            'java',
            'npm',
            'photon',
            'python',
            'rhel',
            'ubuntu',
        ]
        self.assertListEqual(expected, factory.supported_types)
