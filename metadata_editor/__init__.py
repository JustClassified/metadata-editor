"""Interactive image metadata editor package."""

__all__ = ["main"]


def main() -> None:
    """Proxy package-level entrypoint for convenience imports."""
    from .cli import main as cli_main

    cli_main()
