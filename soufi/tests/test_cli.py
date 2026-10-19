# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from unittest import mock

import requests
from click.testing import CliRunner
from testtools.matchers import Contains, Not

from soufi import cli
from soufi.testing import base


class TestCLI(base.TestCase):
    def setUp(self):
        super().setUp()
        self.runner = CliRunner()

    def test_main_uses_legacy_implicit_find_mode(self):
        python = self.patch(cli.Finder, "python")
        python.return_value = mock.Mock(discovery_path=None)

        result = self.runner.invoke(cli.main, ["python", "foo", "1.2.3"])

        self.assertEqual(0, result.exit_code, result.output)
        python.assert_called_once_with(
            "foo", "1.2.3", timeout=30, pyindex=mock.ANY
        )
        self.assertThat(result.output, Contains("deprecated"))

    def test_find_command_still_works_without_deprecation_warning(self):
        python = self.patch(cli.Finder, "python")
        python.return_value = mock.Mock(discovery_path=None)

        result = self.runner.invoke(
            cli.main, ["find", "python", "foo", "1.2.3"]
        )

        self.assertEqual(0, result.exit_code, result.output)
        python.assert_called_once_with(
            "foo", "1.2.3", timeout=30, pyindex=mock.ANY
        )
        self.assertThat(result.output, Not(Contains("deprecated")))

    def test_help_shows_find_subcommand(self):
        result = self.runner.invoke(cli.main, ["--help"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertThat(result.output, Contains("\n  find"))
        self.assertThat(result.output, Contains("history"))

    def test_java_cli_finds_source_from_maven_pom_scm(self):
        source_url = (
            "https://codeload.github.com/example/library/"
            "tar.gz/refs/tags/v2.4.1"
        )
        source_search = mock.Mock(status_code=requests.codes.ok)
        source_search.json.return_value = {"response": {"docs": []}}
        artifact_search = mock.Mock(status_code=requests.codes.ok)
        artifact_search.json.return_value = {
            "response": {
                "docs": [
                    {
                        "g": "org.example",
                        "a": "example-library",
                        "v": "2.4.1",
                    }
                ]
            }
        }
        pom = mock.Mock(
            status_code=requests.codes.ok,
            content=(
                b"<project><scm><connection>"
                b"scm:git:https://github.com/example/library.git"
                b"</connection><tag>v2.4.1</tag></scm></project>"
            ),
        )
        self.patch(
            requests,
            "get",
            mock.Mock(side_effect=[source_search, artifact_search, pom]),
        )
        source_jar_missing = mock.Mock(status_code=requests.codes.not_found)
        archive_found = mock.Mock(
            status_code=requests.codes.ok, url=source_url
        )
        self.patch(
            requests,
            "head",
            mock.Mock(side_effect=[source_jar_missing, archive_found]),
        )

        result = self.runner.invoke(
            cli.main, ["find", "java", "example-library", "2.4.1"]
        )

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(source_url, result.stdout.strip())
        self.assertThat(
            result.stderr,
            Contains("Source discovery path: maven-pom-github-tag-archive"),
        )
