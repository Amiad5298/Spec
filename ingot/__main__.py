"""Entry point for running ingot as a module.

This allows running the application with:
    python -m ingot [OPTIONS] [TICKET]
"""

from ingot.cli import app

if __name__ == "__main__":
    app()
