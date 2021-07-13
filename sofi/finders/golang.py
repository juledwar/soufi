import contextlib
import json
import os
import subprocess  # nosec
from tempfile import TemporaryDirectory
from typing import BinaryIO, ContextManager

from sofi import exceptions, finder


class GolangFinder(finder.SourceFinder):
    """Find Golang modules.

    Golang has a complex set of metadata, indirection and procedures around its
    source module locations. Therefore, this finder is a simple wrapper around
    `go mod download` until we get a more reliable method to
    programmatically do the same thing in Python.

    This finder is also a little different from others. The action of finding
    the source module also downloads it to a local cache instead of "just"
    finding it, because `go mod download` doesn't provide a way to verify the
    target before actually downloading it.

    The URL that is returned in the DiscoveredSource is simply
        package@version
    as this is sufficient to get the module again later from the cache.

    The cache location defaults to the user's GOPATH. If this is not set,
    files will be downloaded to a temporary location that is later cleaned up.
    """

    distro = finder.SourceType.go.value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tmpdir = None

    @property
    def original_url(self):
        return f"{self.name}@{self.version}"

    def _find(self):
        # Main entrypoint from the parent class.
        try:
            data = self._get_module()
        except Exception:
            self._cleanup()
            raise
        location = data.get("Zip")
        return GolangDiscoveredSource(
            [self.original_url], tmpdir=self.tmpdir, zip_path=location
        )

    def _get_module(self):
        """Download a Go source module to cache."""
        # If GOPATH is not set, create a temp space for it.
        gopath = os.environ.get("GOPATH")
        env = os.environ
        if gopath is None:
            self.tmpdir = TemporaryDirectory()
            gopath = self.tmpdir.name
            env = {'GOPATH': gopath, 'PATH': env['PATH']}
        cmd = ['go', 'mod', 'download', '-json', f'{self.original_url}']
        try:
            output = subprocess.run(  # nosec
                cmd, env=env, capture_output=True, check=True
            )
        except subprocess.SubprocessError as e:
            raise exceptions.DownloadError(str(e))
        data = self._parse_json(output.stdout)
        if output.returncode != 0:
            raise exceptions.DownloadError(data['Error'])
        return data

    def _cleanup(self):
        if self.tmpdir is not None:
            self.tmpdir.cleanup()

    def _parse_json(self, data):
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            raise exceptions.DownloadError(str(e))


class GolangDiscoveredSource(finder.DiscoveredSource):
    """A discovered Golang source module.

    The finder already downloaded the module to cache, so this is
    intialised with the path to the module's zip file, which we directly return
    as the archive.

    Deleting an instantiated object will also remove the cache if it was
    created earlier during the find process (ie. GOPATH was not set).
    """

    archive_extension = '.zip'

    def __init__(self, *args, tmpdir, zip_path, **kwargs):
        super().__init__(*args, **kwargs)
        self.zip_path = zip_path
        self.tmpdir = tmpdir

    def populate_archive(self, *args, **kwargs):
        pass  # pragma: no cover

    @contextlib.contextmanager
    def make_archive(self) -> ContextManager[BinaryIO]:
        """Make a context manager to return the zip file's file obj.

        Yields a binary file object to the archive.
        """
        with open(self.zip_path, 'rb') as fd:
            yield fd

    def __repr__(self):
        return self.urls[0]

    def __del__(self):
        if self.tmpdir is not None:
            self.tmpdir.cleanup()
