"""
flare config commands
"""

import click
import secrets
from ...config import load_config


@click.group()
def config() -> None:
    """Manage Flare configuration"""
    pass


@config.command()
def init() -> None:
    """Interactive configuration setup"""
    # Colors
    GREEN = "\033[0;32m"
    NC = "\033[0m"

    click.echo("")
    click.echo("> Set Worker URL")
    worker_url = click.prompt("  URL", default="http://localhost:8787", type=str)

    click.echo("")
    click.echo("> Generating API key")

    # Generate random API key
    generated_key = f"sk_{secrets.token_urlsafe(32)}"
    click.echo(f"  {GREEN}✓{NC} {generated_key}")

    click.echo("")
    click.echo("> Saving configuration")

    # Save configuration
    cfg = load_config()
    cfg.worker_url = worker_url
    cfg.api_key = generated_key
    cfg.save()

    click.echo(f"  {GREEN}✓{NC} ~/.flare/config.json")

    click.echo("")
    click.echo("Set this key as a secret in your Worker:")
    click.echo("  npx wrangler secret put API_KEY")
    click.echo("")


@config.command()
def show() -> None:
    """Show current configuration"""
    # Colors
    DIM = "\033[2m"
    NC = "\033[0m"

    cfg = load_config()

    click.echo("")
    click.echo("> Current Configuration")

    if cfg.worker_url:
        click.echo(f"  Worker URL: {cfg.worker_url}")
    else:
        click.echo("  Worker URL: (not configured)")

    if cfg.api_key:
        # Show masked API key
        masked = "***" + cfg.api_key[-4:] if len(cfg.api_key) > 4 else "***"
        click.echo(f"  API Key: {masked}")
    else:
        click.echo("  API Key: (not configured)")

    # Show config file path if it exists
    if cfg.config_file.exists():
        click.echo(f"  {DIM}{cfg.config_file}{NC}")

    click.echo("")


@config.command("set-url")
@click.argument("url")
def set_url(url: str) -> None:
    """Set the Worker URL"""
    # Colors
    GREEN = "\033[0;32m"
    NC = "\033[0m"

    cfg = load_config()
    cfg.worker_url = url
    cfg.save()

    click.echo("")
    click.echo("> Updating configuration")
    click.echo(f"  {GREEN}✓{NC} Worker URL set to: {url}")
    click.echo("")


@config.command("set-key")
@click.argument("api_key")
def set_key(api_key: str) -> None:
    """Set the API key"""
    # Colors
    GREEN = "\033[0;32m"
    NC = "\033[0m"

    cfg = load_config()
    cfg.api_key = api_key
    cfg.save()

    click.echo("")
    click.echo("> Updating configuration")
    click.echo(f"  {GREEN}✓{NC} API key saved")
    click.echo("")
