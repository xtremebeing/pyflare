"""
Flare CLI main entrypoint
"""

import click
from .commands.run import run
from .commands.config import config


@click.group()
@click.version_option(version="0.1.0", prog_name="flare")
def cli():
    """
    Flare - Serverless Python execution on Cloudflare Sandboxes
    """
    pass


# Add commands
cli.add_command(run)
cli.add_command(config)


if __name__ == "__main__":
    cli()
