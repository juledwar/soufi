# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from testtools.matchers import SameMembers

from soufi.finder import SourceType
from soufi.finders import rhel, yum
from soufi.testing import base


class BaseRHELTest(base.TestCase):
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

    def test_default_repos(self):
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
        self.assertThat(
            finder.get_source_repos(), SameMembers(expected_source)
        )
        self.assertThat(
            finder.get_binary_repos(), SameMembers(expected_binary)
        )
