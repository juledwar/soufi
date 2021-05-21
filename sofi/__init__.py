"""A simple testing CLI to find and download source."""
import shutil

import click

from sofi import exceptions, finder


class Finder:
    @classmethod
    def find(cls, finder):
        source = finder.find()
        click.echo(source)
        return source

    @classmethod
    def ubuntu(cls, name, version):
        click.echo("Logging in to Launchpad")
        ubuntu_finder = finder.factory(
            "ubuntu", name, version, finder.SourceType.os
        )
        click.echo("Finding source in Launchpad")
        return cls.find(ubuntu_finder)

    @classmethod
    def debian(cls, name, version):
        debian_finder = finder.factory(
            "debian", name, version, finder.SourceType.os
        )
        return cls.find(debian_finder)

    @classmethod
    def npm(cls, name, version):
        npm_finder = finder.factory(
            "npm", name, version, finder.SourceType.npm
        )
        return cls.find(npm_finder)

    @classmethod
    def python(cls, name, version, pyindex=None):
        python_finder = finder.factory(
            "python",
            name=name,
            version=version,
            s_type=finder.SourceType.python,
            pyindex=pyindex,
        )
        return cls.find(python_finder)


@click.command()
@click.argument("distro")
@click.argument("name")
@click.argument("version")
@click.option(
    "--pyindex",
    default="https://pypi.org/pypi/",
    help="Python package index if getting Python",
    show_default=True,
)
@click.option(
    "--output",
    "-o",
    help="Download the source archive and write to this file name",
    default=None,
)
@click.option(
    "-O",
    "auto_output",
    is_flag=True,
    default=False,
    help="Download the source archive and write to a default file name."
    "The names vary according to the source type and the archive type, "
    "but will generally follow the format: "
    "{name}-{version}.{distro/type}.tar.[gz|xz] "
    "(This option takes precedence over -o/--output)",
)
def main(distro, name, version, pyindex, output, auto_output):
    """Find and optionally download source files.

    Given a binary name and version, will find and print the URL(s) to the
    source file(s).

    If the --output option is present, the URLs are all downloaded and
    combined into a LZMA-compressed tar file and written to the file
    name specifed.  If the original source is a tarball then that tarball is
    used instead.

    The only sources currently supported are 'debian', 'ubuntu',
    'python' and 'npm', one of which must be specified as the DISTRO
    argument.
    """
    try:
        func = getattr(Finder, distro)
    except AttributeError:
        click.echo(f"{distro} not available")
        click.get_current_context().exit(255)
    try:
        if distro == 'python':
            disc_source = func(name, version, pyindex=pyindex)
        else:
            disc_source = func(name, version)
    except exceptions.SourceNotFound:
        click.echo("source not found")
        click.get_current_context().exit(255)

    if auto_output is not None or output is not None:
        fname = output
        if auto_output:
            fname = f"{name}-{version}.{distro}{disc_source.archive_extension}"
        with disc_source.make_archive() as archive_fd, open(
            fname, 'wb'
        ) as out_fd:
            # copyfileobj copies in chunks, so as not to exhaust memory.
            shutil.copyfileobj(archive_fd, out_fd)


if __name__ == "__main__":
    main()
