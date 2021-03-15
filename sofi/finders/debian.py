import contextlib
import io
import shutil
import tarfile
import tempfile
from pathlib import Path

import requests

from sofi import exceptions, finder

SNAPSHOT_API = "https://snapshot.debian.org/"
API_TIMEOUT = 30  # seconds


class DebianFinder(finder.SourceFinder):
    """Find Debian source files.

    Uses the API documented at
    https://salsa.debian.org/snapshot-team/snapshot/blob/master/API
    """

    distro = finder.Distro.debian.value

    def find(self):
        hashes = self.get_hashes()
        urls = self.get_urls(hashes)
        return DebianDiscoveredSource(urls)

    def get_hashes(self):
        # Return a list of file hashes as used by Snapshot.
        url = f"{SNAPSHOT_API}mr/package/{self.name}/{self.version}/srcfiles"
        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code != requests.codes.ok:
            raise exceptions.SourceNotFound
        data = response.json()
        try:
            return [r['hash'] for r in data['result']]
        except (IndexError, TypeError):
            raise exceptions.SourceNotFound

    def get_urls(self, hashes):
        # Get file name and return (name, url) pairs
        urls = []
        for hash in hashes:
            url = f"{SNAPSHOT_API}mr/file/{hash}/info"
            response = requests.get(url, timeout=API_TIMEOUT)
            if response.status_code != requests.codes.ok:
                raise exceptions.DownloadError(response.reason)
            data = response.json()
            # The result data is a list. I am unsure what each element
            # of the list can be, but it seems like taking the first
            # returns a valid source file name, which is all we want.
            result = data['result'][0]
            name = result['name']
            urls.append((name, f"{SNAPSHOT_API}file/{hash}"))
        return urls


class DebianDiscoveredSource(finder.DiscoveredSource):
    """A discovered Debian source package."""

    def __init__(self, urls):
        names, _urls = zip(*urls)
        super().__init__(_urls)
        self.names = names

    @contextlib.contextmanager
    def make_archive(self):
        # The temp dir is cleaned up once the context manager exits.
        with tempfile.TemporaryDirectory() as target_dir:
            tarfile_fd, tarfile_name = tempfile.mkstemp(dir=target_dir)
            tar = tarfile.open(name=tarfile_name, mode='w:xz')
            self._populate_archive(target_dir, tar)
            with open(tarfile_name, 'rb') as fd:
                yield fd

    def _populate_archive(self, temp_dir, tar):
        for name, url in zip(self.names, self.urls):
            arcfile_name = self._download_file(temp_dir, name, url)
            tar.add(arcfile_name, arcname=name, filter=self._reset_tarinfo)

    def _download_file(self, target_dir, target_name, url):
        tmp_file_name = Path(target_dir) / target_name
        with requests.get(url, stream=True) as response:
            with open(tmp_file_name, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
        return tmp_file_name

    def _reset_tarinfo(self, tarinfo):
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        return tarinfo

    def __repr__(self):
        output = []
        for name, url in zip(self.names, self.urls):
            output.append(f"{name}: {url}")
        return "\n".join(output)
