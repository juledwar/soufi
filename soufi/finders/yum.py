# Copyright (c) 2022 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import abc
import gzip
import pathlib
import pickle
import sys
import textwrap
import warnings
from multiprocessing import Process, Queue
from types import SimpleNamespace

import defusedxml.lxml
import repomd
import requests
from dogpile.cache.backends.null import NullBackend

from soufi import exceptions, finder

warnings.formatwarning = lambda msg, *x, **y: f"WARNING: {msg}\n"


class YumFinder(finder.SourceFinder, metaclass=abc.ABCMeta):
    """An abstract base class for making Yum-based finders.

    Subclasses of this should provide methods for setting up the repository
    search lists to pass to __init__.

    The lookup is a 2-stage process:
        1. Attempt to look up the SRPM directly from the sources repository.
           In these cases, we use the name only and ignore the version,
           since it is a very common practice for repositories to only
           publish repodata for the "current" version, while still
           providing older sources.
        2. Attempt to look up the name of the source RPM from the binary
           repository.  This will catch packages where the source and
           binary package names do not match.  The version is also ignored
           in this step, for the same reasons.  Then backtrack and attempt
           to lookup that package in the source repos.
    """

    def __init__(self, *args, source_repos=None, binary_repos=None, **kwargs):
        self.source_repos = source_repos
        self.binary_repos = binary_repos
        super().__init__(*args, **kwargs)
        if isinstance(self._cache.backend, NullBackend):
            warnings.warn(
                "Use of the Null cache with the DNF/Yum finder is highly "
                "ill-advised.  Please see the documentation.",
                stacklevel=1,
            )

    def generate_repos(self, repos, fallback):
        """Ensure a generator is always returned for repos.

        Either turn the init's value into a generator, or use the fallback
        methods that return the default ones as a generator.
        """
        if repos:
            yield from repos
        else:
            yield from fallback()

    def generate_source_repos(self):
        return self.generate_repos(self.source_repos, self.get_source_repos)

    def generate_binary_repos(self):
        return self.generate_repos(self.binary_repos, self.get_binary_repos)

    @abc.abstractmethod
    def get_source_repos(self):
        raise NotImplementedError  # pragma: nocover

    @abc.abstractmethod
    def get_binary_repos(self):
        raise NotImplementedError  # pragma: nocover

    def _find(self):
        source_url = self.get_source_url()
        return YumDiscoveredSource([source_url], timeout=self.timeout)

    def get_source_url(self):
        """Lookup the URL for the SRPM corresponding to the package name.

        :return: a URL of the location of an SRPM.
        :raises: exceptions.SourceNotFound if no SRPM could be found in any
            of the repos.
        :raises: exceptions.DownloadError on any failure downloading the
            repomd files.  The original exception that caused the failure
            may be inspected in the `__cause__` attribute.
        """
        # NOTE(nic): Try to find the package in the binary repos,
        #  then backtrack into the source repos with the name and version of
        #  the SRPM provided.  This is, in aggregate, faster than looking up
        #  the source first.
        try:
            source_name, source_ver = self._walk_binary_repos(self.name)
        except Exception as e:
            raise exceptions.DownloadError from e
        if source_name is None:
            raise exceptions.SourceNotFound

        try:
            url = self._walk_source_repos(source_name, source_ver)
        except Exception as e:
            raise exceptions.DownloadError from e
        if url is None:
            raise exceptions.SourceNotFound

        # If we have a URL, but it's no good, we don't have a URL.
        if not self.test_url(url):
            raise exceptions.SourceNotFound

        return url

    def _walk_source_repos(self, name, version=None):
        if version is None:
            version = self.version
        locations = set()
        for repo_url in self.generate_source_repos():
            baseurl, repo = self._cache.get_or_create(
                f"repo-{repo_url}",
                do_task,
                creator_args=([get_repomd, repo_url], {}),
            )
            for package in repo.get(name, []):
                # If the package version in the repomd is our version,
                # it's easy.  Note that we want to match epoch-full and
                # epoch-less version formats.
                if version in (package.evr, package.vr):
                    return str(baseurl + package.location)
                # Otherwise let's make it weird
                locations.add(
                    str(package.location.replace(package.vr, version))
                )

                # If we've made it here, things have gotten weird.  Replace the
                # version+release info in all unique package locations with our
                # version and see if they exist.  This should find superseded
                # packages that are present in the repo, but not in the repomd.
                for location in locations:
                    if self.test_url(baseurl + location):
                        return str(baseurl + location)
        return None

    def _walk_binary_repos(self, name):
        packages = set()
        for repo_url in self.generate_binary_repos():
            _, repo = self._cache.get_or_create(
                f"repo-{repo_url}",
                do_task,
                creator_args=([get_repomd, repo_url], {}),
            )
            for package in repo.get(name, []):
                # If we have a binary package matching our version, but
                # with a different name than the corresponding source
                # package, return the NVR fields
                if self.version in (package.evr, package.vr):
                    return self._nevra_or_none(package)
                # Otherwise let's make it weird
                packages.add(self._nevra_or_none(package))

        # If we've made it here, things have gotten weird; this should be
        # the case of a source RPM that produces binary RPMs with different
        # names *and* versions (the lvm2 package from Red Hat is a good example
        # of this).  In this case, we won't be able to make heads or tails of
        # the response, unless (and only unless) it contains a single package.
        try:
            [package] = packages
        except ValueError:
            return None, None
        return package

    def _nevra_or_none(self, package):
        if package.sourcerpm == '':
            # It's here, but has no sources defined!  Bummer...
            return None, None
        nevra = self._get_nevra(str(package.sourcerpm))
        return nevra['name'], f"{nevra['ver']}-{nevra['rel']}"

    # TODO(nic): throw this out and use hawkey/libdnf whenever that finally
    #  stabilizes.  See: https://github.com/juledwar/soufi/issues/13
    @staticmethod
    def _get_nevra(filename):
        """Split out the NEVRA fields from an RPM filename."""

        # It's easiest to do this by eating the filename backwards, dropping
        # offset pointers as we go
        if filename.endswith('.rpm'):
            filename = filename[:-4]
        arch_offset = filename.rfind('.')
        arch = filename[1 + arch_offset :]
        rel_offset = filename[:arch_offset].rfind('-')
        rel = filename[1 + rel_offset : arch_offset]
        ver_offset = filename[:rel_offset].rfind('-')
        ver = filename[1 + ver_offset : rel_offset]
        name = filename[:ver_offset]
        # Sometimes the epoch is before the name, sometimes it's before the
        # version.  Support both.
        if ':' in ver:
            epoch, ver = ver.split(':', maxsplit=1)
        elif ':' in name:
            epoch, name = name.split(':', maxsplit=1)
        else:
            epoch = ''
        return dict(name=name, ver=ver, rel=rel, epoch=epoch, arch=arch)


class YumDiscoveredSource(finder.DiscoveredSource):
    """A discovered Red Hat source package."""

    make_archive = finder.DiscoveredSource.remote_url_is_archive
    archive_extension = '.src.rpm'

    def populate_archive(self, *args, **kwargs):  # pragma: no cover
        # Src RPMs are already compressed archives, nothing to do.
        pass

    def __repr__(self):
        return self.urls[0]


# NOTE(nic): repomd objects require extra-special care and handling.  They
#  are thin wrappers around ElementTree objects, which means they use an
#  obnoxious amount of memory, are notoriously hostile to being pickled,
#  and are also averse to being automagically garbage-collected when they go
#  out of scope.  This puts them at odds with our caching strategy,
#  and makes them less-than-ideal for use inside long-running processes.
#
#  To deal with the dearth of effective memory management, we will run
#  all repomd lookups in subprocesses, that will return any/all "needles"
#  found in the "haystacks" we provide.  This will let the OS
#  efficiently reclaim all the pages used upon completion.
def do_task(target, *args):
    """Run the target callable in a subprocess and return its response."""
    queue = Queue()
    process = Process(target=target, args=(queue,) + args)
    try:
        process.start()
    except RuntimeError as e:
        if 'not using fork' in str(e):
            sys.exit(
                textwrap.dedent(
                    """
                FATAL: Running this finder directly from the global scope is
                not supported on this platform.  To use this finder, call it
                instead from the main module, e.g.:

                   if __name__ == '__main__':
                       soufi.finder.factory(*args, **kwargs).find()

                Aborting."""
                )
            )
        raise
    # We don't want to wait *forever*, but jobs can take several minutes to
    # complete, so wait a relatively long time
    response = queue.get(timeout=600)
    if process.is_alive():
        process.terminate()
    # re-raise exceptions thrown in child processes; this should keep them
    # from getting cached
    if response and isinstance(response[0], Exception):
        raise response[0]
    return response


# NOTE(nic): stolen almost verbatim from repomd.load, except this one:
#  - has timeouts
#  - uses requests instead of urllib to do the heavy lifting
#  - uses `lxml.parse` and file objects instead of `lxml.fromstring`
#  - returns a plain dict instead of a Repo object
def load_repomd(url):
    timeout = YumFinder.timeout
    baseurl = requests.utils.parse_url(url)
    path = pathlib.PurePosixPath(baseurl.path)

    # first we must get the repomd.xml file
    repomd_path = path / 'repodata' / 'repomd.xml'
    repomd_url = baseurl._replace(path=str(repomd_path))

    with requests.get(repomd_url, stream=True, timeout=timeout) as r:
        r.raw.decode_content = True
        repomd_xml = defusedxml.lxml.parse(r.raw)

    # determine the location of *primary.xml.gz from the repomd.xml
    primary_element = repomd_xml.find(
        'repo:data[@type="primary"]/repo:location', namespaces=repomd._ns
    )
    primary_path = path / primary_element.get('href')
    primary_url = baseurl._replace(path=str(primary_path))

    # download and consume *-primary.xml into a dict object for fast lookups.
    # We will use repomd.Package objects rather than reimplement them,
    # but only as an intermediate step (see `serialize_package`, below)
    repo = {}
    with requests.get(primary_url, stream=True, timeout=timeout) as r:
        r.raw.decode_content = True
        with gzip.GzipFile(fileobj=r.raw) as uncompressed:
            for element in defusedxml.lxml.parse(uncompressed).getroot():
                package = repomd.Package(element)
                repo.setdefault(package.name, [])
                repo[package.name].append(serialize_package(package))
    return repo


def get_repomd(queue, url):
    if not url.endswith('/'):
        url += '/'
    try:
        repo = load_repomd(url)
    except Exception as e:
        # Try and send exceptions back to the caller, just like anything
        # else.  It's up to the receiver to inspect and re-raise.  If the
        # exception cannot be serialized, send back a generic Exception.
        try:
            pickle.dumps(e)
        except Exception:
            e = Exception(
                f"Could not serialize {e.__class__.__name__}, "
                f"re-raising as plain Exception with msg: {str(e)}"
            )

        queue.put((e,), timeout=YumFinder.timeout)
        return
    queue.put((url, repo))


# NOTE(nic): repomd.Package object properties do XPath lookups into the
#  ElementTree and other similar tricks on the backend, which makes them
#  unsuitable for the IPC-based workflow we're trying to use, so we'll
#  convert them into simple objects with identical field names so that they
#  can be easily pickled and passed around.  The upside is that we only need
#  to carry over what we need to do package lookups, reducing the space
#  requirements by at least two orders of magnitude.  The downside is that we
#  only get what we've carried over, but in practice that's the opposite of
#  a problem.
def serialize_package(package):
    return SimpleNamespace(
        name=str(package.name),
        version=str(package.version),
        vr=str(package.vr),
        evr=str(package.evr),
        location=str(package.location),
        sourcerpm=str(package.sourcerpm),
    )
