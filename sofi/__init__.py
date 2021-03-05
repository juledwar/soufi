import click

from sofi import exceptions, finder


@click.command()
@click.argument("name")
@click.argument("version")
def main(name, version):
    click.echo("Logging in to Launchpad")
    ubuntu_finder = finder.factory(
        "ubuntu", name, version, finder.SourceType.os
    )
    click.echo("Finding source in Launchpad")
    try:
        disc_source = ubuntu_finder.find()
    except exceptions.SourceNotFound:
        click.echo("source not found")
        click.get_current_context().exit(255)
    click.echo(disc_source.urls)


if __name__ == "__main__":
    main()
