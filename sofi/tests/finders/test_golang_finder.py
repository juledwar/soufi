import json
import os
import tempfile
from unittest import mock

import testtools
from testtools.matchers import Equals
from testtools.matchers._basic import SameMembers

from sofi import exceptions
from sofi.finder import SourceType
from sofi.finders import golang
from sofi.testing import base


class TestGolangFinder(base.TestCase):
    def make_finder(self, name=None, version=None):
        if name is None:
            name = self.factory.make_string('name')
        if version is None:
            version = self.factory.make_string('version')
        kwargs = dict(
            name=name,
            version=version,
            s_type=SourceType.go,
        )
        return golang.GolangFinder(**kwargs)

    def make_data(self, name, version, error_text=None):
        # fmt: off
        return json.dumps({
            "Path": f"github.com/{name}",
            "Version": f"{version}",
            "Info": f"/tmp/pkg/mod/cache/download/github.com/{name}/@v/{version}.info",  # noqa: E501 # nosec
            "GoMod": f"/tmp/pkg/mod/cache/download/github.com/{name}/@v/{version}.mod",  # noqa: E501 # nosec
            "Zip": f"/tmp/pkg/mod/cache/download/github.com/{name}/@v/{version}.zip",  # noqa: E501 # nosec
            "Dir": f"/tmp/pkg/mod/github.com/{name}@{version}",  # nosec
            "Sum": "h1:qml61uy63S6LSDiwDLxTObyKsOm3uUEWfHrFdO8n//w=",
            "GoModSum": "h1:0yGO2rna3S9DkITDWHY1bMtcY4IJ4w+4S+EooZUR0bE=",
            "Error": error_text,
        })
        # fmt: on

    def patch_subprocess_run(
        self,
        name=None,
        version=None,
        returncode=0,
        side_effect=None,
        error_text=None,
        data=None,
    ):
        run = self.patch(golang.subprocess, 'run')
        if side_effect is not None:
            run.side_effect = side_effect
            return run
        output = mock.MagicMock()
        if data is None:
            data = self.make_data(
                name=name, version=version, error_text=error_text
            )
        output.stdout = data
        output.returncode = returncode
        run.return_value = output
        return run

    def test_raises_when_module_not_found(self):
        finder = self.make_finder()
        error_text = self.factory.make_string()
        self.patch_subprocess_run(
            name=finder.name,
            version=finder.version,
            returncode=1,
            error_text=error_text,
        )
        e = self.assertRaises(exceptions.DownloadError, finder.find)
        self.assertEqual(error_text, str(e))

    def test_raises_when_go_cmd_fails(self):
        finder = self.make_finder()
        self.patch_subprocess_run(
            side_effect=golang.subprocess.SubprocessError
        )
        with testtools.ExpectedException(exceptions.DownloadError):
            finder.find()

    def test_cleans_up_tmp_dir_on_failure(self):
        finder = self.make_finder()
        TemporaryDirectory = self.patch(golang, 'TemporaryDirectory')
        tmpdir = mock.MagicMock()
        TemporaryDirectory.return_value = tmpdir
        self.patch_subprocess_run(
            side_effect=golang.subprocess.SubprocessError
        )
        with testtools.ExpectedException(exceptions.DownloadError):
            finder.find()
        tmpdir.cleanup.assert_called_once()

    def test_finds_module(self):
        finder = self.make_finder()
        run = self.patch_subprocess_run(
            name=finder.name, version=finder.version
        )
        source = finder.find()
        expected = [f"{finder.name}@{finder.version}"]
        self.assertThat(source.urls, SameMembers(expected))
        run.assert_called_once_with(
            [
                'go',
                'mod',
                'download',
                '-json',
                f'{finder.name}@{finder.version}',
            ],
            env={'GOPATH': finder.tmpdir.name, 'PATH': os.environ['PATH']},
            capture_output=True,
            check=True,
        )

    def test_raises_for_badly_formed_json(self):
        bad_json = "{foo:foo,,,}"
        finder = self.make_finder()
        self.patch_subprocess_run(
            name=finder.name, version=finder.version, data=bad_json
        )
        with testtools.ExpectedException(exceptions.DownloadError):
            finder.find()


class TestGolangDiscoveredSource(base.TestCase):
    def make_discovered_source(self, url=None, tmpdir=None, zip_path=None):
        if url is None:
            url = self.factory.make_url()
        if tmpdir is None:
            tmpdir = tempfile.TemporaryDirectory()
            self.addCleanup(tmpdir.cleanup)
        if zip_path is None:
            zip_path = self.factory.make_string()
        return golang.GolangDiscoveredSource(
            [url], tmpdir=tmpdir, zip_path=zip_path
        )

    def make_file_with_content(self, target_dir, content: bytes = None):
        if content is None:
            content = self.factory.make_bytes('content')
        _, fake_file = tempfile.mkstemp(dir=target_dir)
        with open(fake_file, 'wb') as fake_file_fd:
            fake_file_fd.write(content)
        return fake_file

    def test_make_archive_yields_existing_zip_file(self):
        content = self.factory.make_bytes()
        with tempfile.TemporaryDirectory() as tmpdir:
            zipfile = self.make_file_with_content(
                target_dir=tmpdir, content=content
            )
            gds = self.make_discovered_source(zip_path=zipfile)
            with gds.make_archive() as archive:
                self.assertThat(archive.read(), Equals(content))

    def test_repr(self):
        url = self.factory.make_url()
        gds = self.make_discovered_source(url=url)
        self.assertEqual(url, repr(gds))

    def test_cleans_up_tmpdir(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        gds = self.make_discovered_source(tmpdir=tmpdir)
        del gds
        self.assertFalse(os.path.exists(tmpdir.name))
