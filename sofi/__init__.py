import sys

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


def urls_debian(name, version):
    debian_finder = finder.factory(
        "debian", name, version, finder.SourceType.os
    )
    disc_source = debian_finder.find()
    click.echo(disc_source)


@click.command()
@click.argument("distro")
@click.argument("name")
@click.argument("version")
def main(distro, name, version):
    if distro == 'debian':
        func = urls_debian
    elif distro == 'ubuntu':
        func = urls_ubuntu
    else:
        click.echo(f"{distro} not available")
        click.get_current_context().exit(255)
    try:
        func(name, version)
    except exceptions.SourceNotFound:
        click.echo("source not found")
        click.get_current_context().exit(255)


if __name__ == "__main__":
    main()
