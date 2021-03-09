from unittest.mock import MagicMock

from sofi.finder import SourceType, factory
from sofi.finders import ubuntu
from sofi.testing import base


class TestFinderFactory(base.TestCase):
    def test_factory_loads_finder_classes(self):
        # Until the finder path is configurable, just check that the
        # Ubuntu finder is present.
        self.assertEqual(
            factory.finders[ubuntu.UbuntuFinder.distro], ubuntu.UbuntuFinder
        )

    def test_factory_passes_args_when_calling(self):
        name = self.factory.make_string()
        version = self.factory.make_string()
        finder_mock = MagicMock()
        factory.finders[ubuntu.UbuntuFinder.distro] = finder_mock
        factory(ubuntu.UbuntuFinder.distro, name, version, SourceType.os)
        finder_mock.assert_called_once_with(name, version, SourceType.os)
