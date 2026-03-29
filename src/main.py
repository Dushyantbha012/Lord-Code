"""
Lord Code - Entry point.

Usage:
    python -m src.main
    lord-code          (after `pip install -e .`)
"""

from src.cli.app import CLIApp


def main() -> None:
    app = CLIApp()
    app.run()


if __name__ == "__main__":
    main()
