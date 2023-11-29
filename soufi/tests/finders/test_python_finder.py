# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from unittest import mock

import requests
import testtools

from soufi import exceptions
from soufi.finder import SourceType
from soufi.finders import python
from soufi.testing import base


class TestPythonFinder(base.TestCase):
    scenarios = [
        ('pypi', dict(index='pypi')),
        ('devpi', dict(index='devpi')),
    ]

    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        kwargs = dict(name=name, version=version, s_type=SourceType.python)
        if self.index == 'devpi':
            kwargs['pyindex'] = self.factory.make_url()
        return python.PythonFinder(**kwargs)

    def make_data(self, version, url, new_style=False):
        if self.index == 'devpi':
            result = dict()
            result['+links'] = []
            result['+links'].append(dict(href=url))
            result['+links'].append(dict(href=self.factory.make_url()))
            return dict(result=result)

        releases = {
            version: [
                dict(packagetype='foobar', url='foobar'),
                dict(packagetype='sdist', url=url),
            ]
        }
        urls = releases[version]

        if new_style:
            return dict(urls=urls)
        return dict(releases=releases)

    def get_requests_call_for_scenario(self, finder):
        if self.index == 'devpi':
            return mock.call(
                f"{finder.index}{finder.name}/{finder.version}",
                headers={'Accept': 'application/json'},
                timeout=30,
            )
        return mock.call(
            f"https://pypi.org/pypi/{finder.name}/{finder.version}/json",
            timeout=30,
        )

    def test_get_source_url(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        data = self.make_data(finder.version, url)

        get = self.patch_get_with_response(requests.codes.ok, json=data)
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        call = self.get_requests_call_for_scenario(finder)
        self.assertIn(call, get.call_args_list)

    def test_get_source_url_new_style(self):
        finder = self.make_finder()
        url = self.factory.make_url()
        data = self.make_data(finder.version, url, new_style=True)

        get = self.patch_get_with_response(requests.codes.ok, json=data)
        found_url = finder.get_source_url()
        self.assertEqual(found_url, url)
        call = self.get_requests_call_for_scenario(finder)
        self.assertIn(call, get.call_args_list)

    def test_get_source_url_source_not_found(self):
        if self.index == 'devpi':
            # devpi returns data or 404.
            self.skipTest("Not applicable to devpi")
        finder = self.make_finder()
        data = self.make_data('badversion', 'foobar')

        self.patch_get_with_response(requests.codes.ok, json=data)
        self.assertRaises(exceptions.SourceNotFound, finder.get_source_url)

    def test_get_source_info_raises_when_response_fails(self):
        self.patch_get_with_response(requests.codes.not_found)
        finder = self.make_finder()
        with testtools.ExpectedException(exceptions.SourceNotFound):
            finder.get_source_url()

    def test_find(self):
        url = self.factory.make_url()
        finder = self.make_finder()
        self.patch(finder, 'get_source_url').return_value = url

        disc_source = finder.find()
        self.assertIsInstance(disc_source, python.PythonDiscoveredSource)
        self.assertEqual([url], disc_source.urls)


class TestPythonDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None):
        if url is None:
            url = self.factory.make_url()
        return python.PythonDiscoveredSource([url])

    def test_repr(self):
        url = self.factory.make_url()
        pds = self.make_discovered_source(url)
        self.assertEqual(url, repr(pds))

    def test_make_archive(self):
        pds = self.make_discovered_source()
        self.assertEqual(pds.make_archive, pds.remote_url_is_archive)
