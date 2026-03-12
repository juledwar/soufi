# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from pathlib import Path

import fixtures
from testtools.matchers import Contains, Equals

from soufi import history_cli
from soufi.testing import base


class TestHistoryCLI(base.TestCase):
    def test_get_release_history_uses_disk_cache(self):
        history = [
            {
                "version": "1.0.0",
                "published_at": "2024-01-01T00:00:00Z",
            }
        ]
        source_finder = self.patch(history_cli.finder, "factory")
        source_finder.return_value.get_release_history.return_value = history
        temp_dir = self.useFixture(fixtures.TempDir()).path
        cache_path = str(Path(temp_dir) / "history-cache.dbm")

        result = history_cli.get_release_history(
            distro="python",
            name="example",
            cache_path=cache_path,
            cache_ttl=111,
            timeout=9,
            pyindex="https://pypi.org/pypi/",
            goproxy="https://proxy.golang.org/",
        )

        self.assertThat(result, Equals(history))
        _, kwargs = source_finder.call_args
        self.assertThat(kwargs["cache_backend"], Equals("dogpile.cache.dbm"))
        self.assertThat(kwargs["cache_ttl"], Equals(111))
        self.assertThat(kwargs["timeout"], Equals(9))
        self.assertThat(kwargs["cache_args"]["filename"], Contains(".dbm"))

    def test_get_release_history_rejects_unknown_type(self):
        temp_dir = self.useFixture(fixtures.TempDir()).path
        cache_path = str(Path(temp_dir) / "x.dbm")
        self.assertRaises(
            ValueError,
            history_cli.get_release_history,
            distro="nope",
            name="example",
            cache_path=cache_path,
            cache_ttl=1,
            timeout=1,
            pyindex="x",
            goproxy="x",
        )

    def test_get_release_history_passes_go_proxy_for_go(self):
        source_finder = self.patch(history_cli.finder, "factory")
        source_finder.return_value.get_release_history.return_value = []
        temp_dir = self.useFixture(fixtures.TempDir()).path
        cache_path = str(Path(temp_dir) / "history-cache.dbm")

        history_cli.get_release_history(
            distro="go",
            name="example/module",
            cache_path=cache_path,
            cache_ttl=111,
            timeout=9,
            pyindex="https://pypi.org/pypi/",
            goproxy="https://proxy.example.invalid/",
        )

        _, kwargs = source_finder.call_args
        self.assertThat(
            kwargs["goproxy"], Equals("https://proxy.example.invalid/")
        )
