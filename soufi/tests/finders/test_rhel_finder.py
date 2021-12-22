# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from soufi.finder import SourceType
from soufi.finders import rhel, yum
from soufi.testing import base


class BaseRHELTest(base.TestCase):
    def setUp(self):
        super().setUp()
        yum.YumFinder._get_repo.cache_clear()
        yum.YumFinder._get_url.cache_clear()

    def make_finder(self, name=None, version=None, **kwargs):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        if 'source_repos' not in kwargs:
            kwargs['source_repos'] = ['']
        if 'binary_repos' not in kwargs:
            kwargs['binary_repos'] = ['']
        return rhel.RHELFinder(name, version, SourceType.os, **kwargs)

    def test_find(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        self.patch(finder, 'get_source_url').return_value = url
        disc_source = finder.find()
        self.assertIsInstance(disc_source, yum.YumDiscoveredSource)
        self.assertEqual([url], disc_source.urls)

    def test_initializer_uses_defaults_when_called_with_no_args(self):
        name = self.factory.make_string('name')
        version = self.factory.make_string('version')
        finder = rhel.RHELFinder(name, version, SourceType.os)
        expected_source = [
            f"{rhel.DEFAULT_REPO}/{dir}/source/SRPMS"
            for dir in rhel.RHELFinder.default_search_dirs
        ]
        expected_binary = [
            f"{rhel.DEFAULT_REPO}/{dir}/os"
            for dir in rhel.RHELFinder.default_search_dirs
        ]
        self.assertEqual(expected_source, finder.source_repos)
        self.assertEqual(expected_binary, finder.binary_repos)
