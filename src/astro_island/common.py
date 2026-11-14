"""Общий код острова и приложения настроек: конфиг, палитра, русские даты."""
import json
import os
import re
import sys
from pathlib import Path

APP_NAME = "DynamicIslandRU"
CFG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
CFG_FILE = CFG_DIR / "config.json"
SHELF_FILE = CFG_DIR / "shelf.json"
REMINDERS_FILE = CFG_DIR / "reminders.json"
LYRICS_DIR = CFG_DIR / "lyrics"   # кэш найденных текстов
QUIT_FLAG = CFG_DIR / "quit.flag"        # настройки кладут сюда файл — остров видит его и закрывается
CLIP_FILE = CFG_DIR / "clipboard.json"   # история буфера обмена
CLIP_DIR = CFG_DIR / "clips"             # картинки из истории буфера


# ───────── запуск самой программы (из исходников и из сборки Nuitka) ─────────
def is_compiled() -> bool:
    """True, если это собранный exe (Nuitka/PyInstaller), а не запуск из исходников."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def self_argv(settings: bool = False) -> list:
    """Команда запуска второго экземпляра: сборка — сам exe, исходники — python -m."""
    if is_compiled():
        return [sys.executable, "--settings"] if settings else [sys.executable]
    module = "astro_island.settings_app" if settings else "astro_island"
    return [sys.executable, "-m", module]


def self_command(settings: bool = False) -> str:
    """Та же команда строкой (для реестра автозапуска)."""
    return " ".join(f'"{a}"' for a in self_argv(settings))

# ───────── темы острова ─────────
# Параметры темы. У готовых тем (чёрная, белая) меняются только цвета, у «своей» — всё, что ниже.
THEME_BASE = {
    "bg": "#000000",            # цвет фона
    "fg": "#ffffff",            # цвет текста и значков
    "alpha": 100,               # доля непрозрачности самой темы, % (общий ползунок «Непрозрачность фона» работает поверх)
    "gradient": False,          # фон — градиент от bg к bg2
    "bg2": "#1b1b2f",
    "gradient_dir": "v",        # v — сверху вниз, h — слева направо, d — наискосок
    "glass": False,             # эффект стекла: блик сверху и светлая кромка
    "glass_strength": 60,       # 10..100
    "glow": False,              # подсветка: цветное свечение по краю внутрь острова
    "glow_strength": 50,        # 10..100
    "glow_color": "#4d7cff",
}
THEMES = {  # ключ: (название, что переопределяет)
    "black": ("Чёрная", {}),
    "white": ("Белая", {"bg": "#f5f5f7", "fg": "#1c1c1e"}),
}
CUSTOM_THEME_DEFAULT = dict(THEME_BASE, bg="#12131c", fg="#f5f5f7", gradient=True, bg2="#2b1f55",
                            glass=True, glow=True, glow_color="#7c6cf0")
_HEX6 = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULTS = {
    "style": "pill",            # "notch" (свисает сверху) | "pill" (плавающая таблетка)
    "border": "aurora",         # ключ из BORDERS или "custom"
    "custom_color": "#ff6b6b",
    "thickness": "medium",      # thin | medium | thick
    "moving_gradient": False,
    "opacity": 100,             # 50..100, прозрачность чёрного фона
    "expand_on": "hover",       # hover | click
    "top_margin": 10,           # отступ от верха (только для pill)
    "show_seconds": True,
    "clock_24h": True,
    "week_starts_monday": True,
    "mascot": "eye",            # кто следит за курсором на острове: eye|ghost|panda|fox|alien|creeper|skull|none
    "repo_color": "#6e7f6e",    # цвет персонажа R.E.P.O
    "rest_show": "both",        # что в покое: both (персонаж и время) | mascot | time
    "autohide": False,          # прятать остров за верхний край в покое; появляется, когда курсор у верха экрана
    "lyrics_on": True,          # бегущий текст песни на острове в покое (Live Lyrics)
    "lyrics_offset_ms": 0,      # ручной сдвиг синхронизации текста
    "alarm_sound": True,        # звук на таймере и напоминаниях
    "click_ripple": True,       # расходящийся круг в месте клика по острову
    "tab_ripple": True,         # круговая анимация при переключении вкладок
    "rec_mode": "sys",          # запись экрана: screen (только экран) | sys (+звук ПК) | sysmic (+микрофон)
    "rec_fps": 30,              # 24 | 30 | 60
    "rec_cursor": True,         # показывать курсор на записи
    "rec_dir": "",              # папка для записей и скриншотов ("" — Видео / Изображения \ DynamicIsland)
    "monitor": "main",          # на каком мониторе остров: main (основной) | second (второй) | both (на всех)
    "downloads_on": True,       # показывать на острове загрузки в браузере
    "downloads_dir": "",        # папка загрузок ("" — найти системную)
    "theme": "black",           # black | white | custom
    "theme_custom": dict(CUSTOM_THEME_DEFAULT),
    "weather_on": True,         # погода на вкладке «Часы»
    "weather_city": "",         # город для погоды ("" — определить автоматически по IP)
    "clip_pause": False,        # история буфера: запись на паузе
    "clip_persist": True,       # история буфера: хранить на диске между запусками
    "modules": {"clock": True, "timer": True, "reminders": True, "calc": True, "system": True, "eye": False, "shelf": True,
                "music": True, "clip": True, "rec": True, "mixer": True},
}

THICKNESS = {"thin": 1.5, "medium": 2.5, "thick": 4.0}

# ключ: (название, цвета по кругу — последний равен первому)
BORDERS = {
    "black":  ("Чёрная",    ["#000000"]),
    "aurora": ("Аврора",    ["#ff6b6b", "#c44dff", "#4d7cff", "#ff6b6b"]),
    "ocean":  ("Океан",     ["#3d7bff", "#2fe0c0", "#3d7bff"]),
    "sunset": ("Закат",     ["#ff8a5c", "#ff5f8a", "#ff8a5c"]),
    "azure":  ("Лазурь",    ["#0090ff", "#00d5ff", "#0090ff"]),
    "amber":  ("Янтарь",    ["#e8955f", "#f4cf9b", "#e8955f"]),
    "violet": ("Фиолет",    ["#b100ff", "#5a3dff", "#b100ff"]),
    "silver": ("Серебро",   ["#ffffff", "#8a8a8a", "#ffffff"]),
}

MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль",
          "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
              "августа", "сентября", "октября", "ноября", "декабря"]
WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _mix(hex_color: str, target: int, k: float) -> str:
    hex_color = hex_color.lstrip("#")
    rgb = [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]
    rgb = [round(c + (target - c) * k) for c in rgb]
    return "#%02x%02x%02x" % tuple(rgb)


def media_dir(cfg, kind: str) -> Path:
    """Куда складывать записи экрана (kind="video") и скриншоты (kind="shot")."""
    custom = str(cfg.get("rec_dir") or "").strip()
    if custom:
        return Path(custom)
    return Path.home() / ("Videos" if kind == "video" else "Pictures") / "DynamicIsland"


def is_light(hex_color: str) -> bool:
    """Светлый ли цвет (по воспринимаемой яркости)."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.58
    except Exception:
        return False


def theme_name(cfg) -> str:
    if cfg.get("theme") == "custom":
        return "Своя"
    return THEMES.get(cfg.get("theme"), THEMES["black"])[0]


def resolve_theme(cfg) -> dict:
    """Итоговые параметры темы (все ключи THEME_BASE заполнены и проверены)."""
    key = cfg.get("theme", "black")
    th = dict(THEME_BASE)
    if key == "custom":
        th.update({k: v for k, v in (cfg.get("theme_custom") or {}).items() if k in THEME_BASE})
    elif key in THEMES:
        th.update(THEMES[key][1])
    for k in ("bg", "bg2", "fg", "glow_color"):
        if not (isinstance(th[k], str) and _HEX6.match(th[k])):
            th[k] = THEME_BASE[k]
    for k, lo, hi in (("alpha", 10, 100), ("glass_strength", 10, 100), ("glow_strength", 10, 100)):
        try:
            th[k] = max(lo, min(hi, int(th[k])))
        except Exception:
            th[k] = THEME_BASE[k]
    th["gradient_dir"] = th["gradient_dir"] if th["gradient_dir"] in ("v", "h", "d") else "v"
    for k in ("gradient", "glass", "glow"):
        th[k] = bool(th[k])
    return th


def border_name(cfg) -> str:
    if cfg["border"] == "custom":
        return "Свой цвет"
    return BORDERS.get(cfg["border"], BORDERS["aurora"])[0]


def border_colors(cfg) -> list:
    if cfg["border"] == "custom":
        c = cfg.get("custom_color", "#ff6b6b")
        return [c, _mix(c, 255, 0.45), c]
    return list(BORDERS.get(cfg["border"], BORDERS["aurora"])[1])


def is_black(colors) -> bool:
    return all(c.lower() == "#000000" for c in colors)


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        data = json.loads(CFG_FILE.read_text("utf-8"))
        for k, v in data.items():
            if k == "modules" and isinstance(v, dict):
                cfg["modules"].update(v)
            elif k == "theme_custom" and isinstance(v, dict):
                cfg["theme_custom"].update(v)
            elif k in cfg:
                cfg[k] = v
    except Exception:
        pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CFG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
        os.replace(tmp, CFG_FILE)
    except Exception as e:  # файл мог быть занят — не страшно, следующая запись пройдёт
        print("Не удалось сохранить настройки:", e)


def config_mtime() -> int:
    try:
        return CFG_FILE.stat().st_mtime_ns
    except Exception:
        return 0
