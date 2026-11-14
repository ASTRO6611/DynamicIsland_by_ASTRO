"""Точка входа для сборки Nuitka (и обычного запуска из исходников).

    python main.py              # остров
    python main.py --settings   # окно настроек

Собранный exe запускает сам себя с флагом ``--settings`` — так же, как
исходники запускают ``python -m astro_island.settings_app``.
"""
import sys
from pathlib import Path

try:  # пакет установлен (uv sync) — src в sys.path не нужен
    import astro_island  # noqa: F401
except ImportError:  # запуск прямо из папки проекта
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from astro_island.cli import island, settings


def main() -> int:
    want_settings = "--settings" in sys.argv[1:]
    sys.argv[1:] = [a for a in sys.argv[1:] if a != "--settings"]
    return settings() if want_settings else island()


if __name__ == "__main__":
    sys.exit(main())
