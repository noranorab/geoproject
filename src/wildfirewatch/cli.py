import click

from wildfirewatch.ingest.cli import ingest
from wildfirewatch.processing.cli import process


@click.group()
def cli():
    """WildfireWatch pipeline CLI."""


cli.add_command(ingest)
cli.add_command(process)


if __name__ == "__main__":
    cli()
