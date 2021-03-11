import functools
import pathlib

from launchpadlib.launchpad import Launchpad

from sofi import exceptions, finder


class UbuntuFinder(finder.SourceFinder):
    """Find Ubuntu source files."""

    distro = finder.Distro.ubuntu.value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lp_archive = self.get_archive()

    def find(self):
        build = self.get_build()
        source = self.get_source_from_build(build)
        urls = tuple(sorted(source.sourceFileUrls()))
        return UbuntuDiscoveredSource(urls)

    @classmethod
    @functools.lru_cache
    def get_archive(cls):
        """Retrieve, and cache, the LP distro main archive object."""
        cachedir = pathlib.Path.home().joinpath(".launchpadlib", "cache")
        lp = Launchpad.login_anonymously(
            "sofi", "production", cachedir, version="devel"
        )
        distribution = lp.distributions[cls.distro]
        return distribution.main_archive

    def get_build(self):
        bins = self.lp_archive.getPublishedBinaries(
            exact_match=True, binary_name=self.name, version=self.version
        )
        try:
            return bins[0].build
        except IndexError:
            raise exceptions.SourceNotFound

    def get_source_from_build(self, build):
        name = build.source_package_name
        ver = build.source_package_version
        sources = self.lp_archive.getPublishedSources(
            exact_match=True, source_name=name, version=ver
        )
        # TODO index error? Can't have a build without a source so this
        # should never fail.
        return sources[0]


class UbuntuDiscoveredSource(finder.DiscoveredSource):
    """A discovered Ubuntu source package."""

    def make_archive(self):
        # TODO
        pass

    def __repr__(self):
        return "\n".join(self.urls)
