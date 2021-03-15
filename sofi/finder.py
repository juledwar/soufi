import abc
import contextlib
import enum
import importlib
import pkgutil
from inspect import isclass
from typing import BinaryIO, Iterable, Union


@enum.unique
class SourceType(enum.Enum):
    os = "os"
    python = "python"
    npm = "npm"
    gem = "gem"
    java = "java"
    go = "go"
    nuget = "nuget"


@enum.unique
class Distro(enum.Enum):
    debian = "debian"
    ubuntu = "ubuntu"
    rhel = "rhel"


class DiscoveredSource(metaclass=abc.ABCMeta):
    """Base class for all objects implementing a discovered source."""

    def __init__(self, urls: Iterable[str]):
        self._urls = urls

    @property
    def urls(self):
        return self._urls

    @abc.abstractmethod
    def make_archive(self) -> contextlib.AbstractContextManager[BinaryIO]:
        raise NotImplementedError  # pragma: no cover


class SourceFinder(metaclass=abc.ABCMeta):
    """Base class for all objects that implement source finding."""

    @property
    @abc.abstractmethod
    def distro(self) -> Union[Distro, str]:
        raise NotImplementedError  # pragma: no cover

    def __init__(self, name: str, version: str, s_type: SourceType):
        self.name = name
        self.version = version
        self.s_type = s_type

    @abc.abstractmethod
    def find(self) -> DiscoveredSource:
        raise NotImplementedError  # pragma: no cover


class FinderFactory:
    """Factory singleton to return Finder objects.

    Once instantiated, call as:
        factory('<type>', arg1, arg2...)
    Where <type> is a known Finder type (e.g. 'ubuntu') and the rest of the
    args/kwargs are passed direction to the Finder's __init__.
    """

    def __init__(self):
        self.finders = dict()
        # TODO: Make this path configurable.
        import sofi.finders

        for _, module, _ in pkgutil.iter_modules(sofi.finders.__path__):
            mod = importlib.import_module(f"sofi.finders.{module}")
            for _name, obj in mod.__dict__.items():
                if isclass(obj) and issubclass(obj, SourceFinder):
                    # Add class object to our dict.
                    self.finders[obj.distro] = obj

    def __call__(
        self, distro: Union[Distro, str], *args, **kwargs
    ) -> SourceFinder:
        return self.finders[distro](*args, **kwargs)


factory = FinderFactory()
