"""Entry point for ``python -m astro_island``."""
import sys

from .cli import island

if __name__ == "__main__":
    sys.exit(island())
