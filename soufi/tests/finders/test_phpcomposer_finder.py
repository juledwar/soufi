# Copyright (c) 2024 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import json
from pathlib import Path
from unittest import mock

import requests

from soufi import exceptions, testing
from soufi.finder import SourceType
from soufi.finders import php_composer
from soufi.testing import base


class TestPHPPECLFinder(base.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.testing = Path(testing.__path__[0]) / 'data' / 'phpcomposer'

    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string("name")
        if version is None:
            version = self.factory.make_string("version")
        kwargs = dict(
            name=name, version=version, s_type=SourceType.phpcomposer
        )
        return php_composer.PHPComposer(**kwargs)

    def test_get_source_url(self):
        # The test data uses this package.
        finder = self.make_finder("monolog/monolog", "2.3.5")
        expected_url = self.factory.make_url()
        expected_type = self.factory.random_choice(["zip", "tgz", "tar.gz"])
        with open(self.testing / "monolog.json", "rb") as fp:
            data = json.load(fp)
        # Patch the real URL with our random one to make sure it's correctly
        # picked up later.
        for version in data["packages"]["monolog/monolog"]:
            if version["version"] == "2.3.5":
                version["dist"]["url"] = expected_url
                version["dist"]["type"] = expected_type
                break
        get = self.patch_get_with_response(requests.codes.ok, json=data)

        found_url, found_type = finder.get_source_url()
        self.assertEqual(expected_url, found_url)
        self.assertEqual(expected_type, found_type)
        call = mock.call(
            f"{php_composer.DEFAULT_INDEX}p2/{finder.name}.json",
            timeout=30,
        )
        self.assertIn(call, get.call_args_list)

    def test_get_source_url_source_not_found(self):
        finder = self.make_finder()
        self.patch_get_with_response(requests.codes.not_found)
        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)

    def test_get_source_version_not_found(self):
        finder = self.make_finder("monolog/monolog")
        with open(self.testing / "monolog.json", "rb") as fp:
            data = json.load(fp)
        self.patch_get_with_response(requests.codes.ok, json=data)
        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)

    def test_get_source_url_malformed_json(self):
        finder = self.make_finder()
        self.patch_get_with_response(requests.codes.ok, data="not json")
        self.assertRaises(exceptions.DownloadError, finder.get_source_url)

    def test_find(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        atype = self.factory.random_choice(["zip", "tgz", "tar.gz"])
        self.patch(finder, "get_source_url").return_value = url, atype

        disc_source = finder.find()
        self.assertIsInstance(
            disc_source, php_composer.PHPComposerDiscoveredSource
        )
        self.assertEqual([url], disc_source.urls)
        self.assertEqual(f".{atype}", disc_source.archive_extension)


class TestPHPPECLDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None, atype=None):
        if url is None:
            url = self.factory.make_url()
        if atype is None:
            atype = self.factory.random_choice([".zip", ".tgz", ".tar.gz"])
        return php_composer.PHPComposerDiscoveredSource(
            [url], archive_extension=atype
        )

    def test_repr(self):
        url = self.factory.make_url()
        atype = self.factory.random_choice([".zip", ".tgz", ".tar.gz"])
        ds = self.make_discovered_source(url, atype)
        self.assertEqual(f"{url}: {atype}", repr(ds))

    def test_make_archive(self):
        ds = self.make_discovered_source()
        self.assertEqual(ds.make_archive, ds.remote_url_is_archive)
