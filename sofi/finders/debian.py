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

    def make_archive(self):
        # TODO
        pass

    def __repr__(self):
        output = []
        for name, url in zip(self.names, self.urls):
            output.append(f"{name}: {url}")
        return "\n".join(output)
