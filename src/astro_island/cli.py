"""Entry points for the astro-island package.

Each function is referenced from ``[project.scripts]`` in ``pyproject.toml``,
so the applications start with standard commands::

    uv run astro-island           # the island overlay
    uv run astro-island-settings  # the settings window
"""
from __future__ import annotations


def island() -> int:
    """Launch the Dynamic Island overlay."""
    from .island import main as _run_island  # импорт здесь: остров подменяет цвета под тему, настройкам это не нужно
    return _run_island()


def settings() -> int:
    """Launch the settings window."""
    from .settings_app import main as _run_settings
    return _run_settings()
