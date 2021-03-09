import testtools
from testtools.matchers import Equals

from sofi.finder import SourceFinder, SourceType
from sofi.testing import base


class TestSourceFinderBase(base.TestCase):
    def test_stores_init_params(self):
        class TestFinder(SourceFinder):
            def distro(self):
                pass

            def find(self):
                pass

        name = self.factory.make_string()
        version = self.factory.make_string()
        s_type = self.factory.pick_enum(SourceType)
        sf = TestFinder(name, version, s_type)
        self.expectThat(sf.name, Equals(name))
        self.expectThat(sf.version, Equals(version))
        self.expectThat(sf.s_type, Equals(s_type))

    def test_requires_distro_property(self):
        class TestFinder(SourceFinder):
            def find(self):
                pass

        name = self.factory.make_string()
        version = self.factory.make_string()
        s_type = self.factory.pick_enum(SourceType)
        with testtools.ExpectedException(TypeError) as e:
            TestFinder(name, version, s_type)
            self.assertIn('abstract methods distro', str(e))

    def test_requires_find_method(self):
        class TestFinder(SourceFinder):
            def distro(self):
                pass

        name = self.factory.make_string()
        version = self.factory.make_string()
        s_type = self.factory.pick_enum(SourceType)
        with testtools.ExpectedException(TypeError) as e:
            TestFinder(name, version, s_type)
            self.assertIn('abstract methods find', str(e))
