"""A simple testing CLI to find and download source."""
import shutil

import click

from sofi import exceptions, finder


def urls_ubuntu(name, version):
    click.echo("Logging in to Launchpad")
    ubuntu_finder = finder.factory(
        "ubuntu", name, version, finder.SourceType.os
    )
    click.echo("Finding source in Launchpad")
    disc_source = ubuntu_finder.find()
    click.echo(disc_source)
    return disc_source


def urls_debian(name, version):
    debian_finder = finder.factory(
        "debian", name, version, finder.SourceType.os
    )
    disc_source = debian_finder.find()
    click.echo(disc_source)
    return disc_source


def urls_npm(name, version):
    npm_finder = finder.factory("npm", name, version, finder.SourceType.npm)
    disc_source = npm_finder.find()
    click.echo(disc_source)
    return disc_source


@click.command()
@click.argument("distro")
@click.argument("name")
@click.argument("version")
@click.option(
    "--output",
    "-o",
    help="Download the source archive and write to this file name",
    default=None,
)
def main(distro, name, version, output):
    """Find and optionally download source files.

    Given a binary name and version, will find and print the URL(s) to the
    source file(s).

    If the --output option is present, the URLs are all downloaded and
    combined into a LZMA-compressed tar file and written to the file
    name specifed.  If the original source is a tarball then that tarball is
    used instead.

    The only sources currently supported are 'debian', 'ubuntu', and 'npm', one
    of which must be specified as the DISTRO argument.
    """
    if distro == 'debian':
        func = urls_debian
    elif distro == 'ubuntu':
        func = urls_ubuntu
    elif distro == 'npm':
        func = urls_npm
    else:
        click.echo(f"{distro} not available")
        click.get_current_context().exit(255)
    try:
        disc_source = func(name, version)
    except exceptions.SourceNotFound:
        click.echo("source not found")
        click.get_current_context().exit(255)

    if output is not None:
        with disc_source.make_archive() as archive_fd:
            with open(output, 'wb') as out_fd:
                # copyfileobj copies in chunks, so as not to exhaust memory.
                shutil.copyfileobj(archive_fd, out_fd)


if __name__ == "__main__":
    main()
