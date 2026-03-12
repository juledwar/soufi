# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates
# All rights reserved.

from unittest import mock

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
        python.return_value = object()

        result = self.runner.invoke(cli.main, ["python", "foo", "1.2.3"])

        self.assertEqual(0, result.exit_code, result.output)
        python.assert_called_once_with(
            "foo", "1.2.3", timeout=30, pyindex=mock.ANY
        )
        self.assertThat(result.output, Contains("deprecated"))

    def test_find_command_still_works_without_deprecation_warning(self):
        python = self.patch(cli.Finder, "python")
        python.return_value = object()

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
