"""Темы острова.

Две задачи:

1. ``paint_surface`` — рисует фон острова по параметрам темы: цвет или градиент, эффект стекла,
   внутреннюю подсветку по краю. Им пользуются и сам остров, и превью в настройках.

2. ``install`` — подгоняет под тему цвета интерфейса, которые зашиты прямо в код вкладок
   (белый текст, серые кнопки, тёмные карточки). Без этого на светлом фоне получился бы белый текст
   по белому. Все «нейтральные» (серые) цвета раскладываются между цветом фона темы и цветом
   текста темы: чёрное становится цветом фона, белое — цветом текста, серое — чем-то между.
   Цветные акценты (красный, зелёный, синий…) не трогаются.

   Для стандартной чёрной темы подмена выключена вообще — остров работает ровно как раньше.
   ``install()`` нужно вызвать ДО импорта модулей, которые делают ``from PySide6.QtGui import QColor``.
"""
import re
import sys

from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor as RealQColor, QLinearGradient, QPen

from . import common as C

_S = {"bg": (0, 0, 0), "fg": (255, 255, 255), "on": False, "key": ("#000000", "#ffffff", "")}
_SKIP_MODULES = ("island_snip",)    # окно скриншотов всегда остаётся тёмным
_SAT_LIMIT = 28                     # разброс каналов больше этого — цвет считаем акцентным и не трогаем


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _key(th):
    """От чего зависит подмена цветов: фон, текст и (для градиента) второй цвет фона."""
    return (th["bg"], th["fg"], th["bg2"] if th["gradient"] else "")


def configure(cfg=None) -> dict:
    """Читает тему из конфига и запоминает, от каких цветов зависит подмена."""
    th = C.resolve_theme(cfg if cfg is not None else C.load_config())
    bg, fg = _rgb(th["bg"]), _rgb(th["fg"])
    if th["gradient"]:
        # у градиентной темы кнопки и карточки подгоняем под СРЕДНИЙ тон фона, а не под самый тёмный край,
        # иначе на фиолетовом/цветном острове они выглядят чёрными
        bg = tuple(round((a + b) / 2) for a, b in zip(bg, _rgb(th["bg2"])))
    _S["bg"], _S["fg"] = bg, fg
    _S["on"] = _S["bg"] != (0, 0, 0) or _S["fg"] != (255, 255, 255)
    _S["key"] = _key(th)
    return th


def base_changed(cfg) -> bool:
    """True, если у новой темы другой цвет фона или текста: подмену цветов приходится делать заново,
    а значит, острову нужен перезапуск."""
    return _key(C.resolve_theme(cfg)) != _S["key"]


def bg_rgb():
    return _S["bg"]


def fg_rgb():
    return _S["fg"]


def is_light(hex_color: str) -> bool:
    return C.is_light(hex_color)


# ───────── подмена цветов ─────────
def map_rgb(r, g, b):
    if not _S["on"] or max(r, g, b) - min(r, g, b) > _SAT_LIMIT:
        return r, g, b
    t = (r + g + b) / 765.0
    bg, fg = _S["bg"], _S["fg"]
    return tuple(round(bg[i] + (fg[i] - bg[i]) * t) for i in range(3))


# #rgb / #rrggbb / #aarrggbb; не трогаем селекторы вида «#banner{» и «#card QLabel»
_HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])(?!\s*[{A-Za-z#.:\[>])")
_RGBA = re.compile(r"(rgba?)\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(,\s*[\d.]+%?\s*)?\)")


def _hex_sub(m):
    s = m.group(1)
    alpha = ""
    if len(s) == 8:
        alpha, s = s[:2], s[2:]
    elif len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    r, g, b = map_rgb(int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    return "#%s%02x%02x%02x" % (alpha, r, g, b)


def _rgba_sub(m):
    r, g, b = map_rgb(min(255, int(m.group(2))), min(255, int(m.group(3))), min(255, int(m.group(4))))
    return "%s(%d,%d,%d%s)" % (m.group(1), r, g, b, m.group(5) or "")


def remap_qss(qss: str) -> str:
    return _RGBA.sub(_rgba_sub, _HEX.sub(_hex_sub, qss))


def _caller_skipped(depth: int) -> bool:
    try:
        return sys._getframe(depth).f_globals.get("__name__", "").endswith(_SKIP_MODULES)
    except Exception:
        return False


class _ThemedColor(RealQColor):
    """QColor, который при создании из строки («#ffffff») подгоняет нейтральные цвета под тему.
    Цвета, заданные числами (QColor(0, 0, 0, 90)) не трогаются — это тени и прозрачные слои."""

    def __init__(self, *args):
        if len(args) == 1 and isinstance(args[0], RealQColor):
            # копия другого QColor: конструктор-копия у подкласса в PySide6 путается с QVariant
            # («QVariant must be holding a QColor»), поэтому копируем значения вручную
            src = args[0]
            super().__init__()
            if src.isValid():
                self.setRgbF(src.redF(), src.greenF(), src.blueF(), src.alphaF())
            return
        if _S["on"] and len(args) == 1 and isinstance(args[0], str) and not _caller_skipped(2):
            c = RealQColor(args[0])
            if c.isValid():
                r, g, b = map_rgb(c.red(), c.green(), c.blue())
                super().__init__(r, g, b, c.alpha())
                return
        super().__init__(*args)


_orig_set_qss = QtWidgets.QWidget.setStyleSheet


def _set_qss(self, qss):
    if _S["on"] and isinstance(qss, str) and not _caller_skipped(2):
        qss = remap_qss(qss)
    return _orig_set_qss(self, qss)


def install():
    """Включить подмену цветов (если активная тема её требует). Вызывать один раз, в самом начале."""
    if getattr(install, "done", False):
        return
    install.done = True
    configure()
    if not _S["on"]:
        return
    _ThemedColor.__name__ = "QColor"
    QtGui.QColor = _ThemedColor
    QtWidgets.QWidget.setStyleSheet = _set_qss


# ───────── рисование фона ─────────
def paint_surface(p, path, vis, th, opacity, glow_color=None, edge=False):
    """Фон острова.
    p — QPainter; path — форма острова; vis — видимая часть (QRectF); th — resolve_theme();
    opacity — общий ползунок «Непрозрачность» (50..100); glow_color — цвет подсветки (#rrggbb);
    edge — тонкий тёмный кант (для светлых тем, когда рамка выключена)."""
    a = round(255 * max(50, min(100, int(opacity))) / 100 * th["alpha"] / 100)
    c1 = RealQColor(th["bg"])
    c1.setAlpha(a)
    if th["gradient"]:
        c2 = RealQColor(th["bg2"])
        c2.setAlpha(a)
        d = th["gradient_dir"]
        if d == "h":
            g = QLinearGradient(vis.topLeft(), vis.topRight())
        elif d == "d":
            g = QLinearGradient(vis.topLeft(), vis.bottomRight())
        else:
            g = QLinearGradient(vis.topLeft(), vis.bottomLeft())
        g.setColorAt(0, c1)
        g.setColorAt(1, c2)
        p.fillPath(path, QBrush(g))
    else:
        p.fillPath(path, c1)

    p.save()
    p.setClipPath(path)
    if th["glass"]:
        s = th["glass_strength"] / 100.0
        light = is_light(th["bg"])
        g = QLinearGradient(vis.topLeft(), vis.bottomLeft())
        g.setColorAt(0.0, RealQColor(255, 255, 255, int(120 * s)))
        g.setColorAt(0.5, RealQColor(255, 255, 255, int(16 * s)))
        g.setColorAt(1.0, RealQColor(0, 0, 0, int(34 * s)) if light else RealQColor(255, 255, 255, int(8 * s)))
        p.fillRect(vis, QBrush(g))
    if th["glow"] and glow_color:
        s = th["glow_strength"] / 100.0
        col = RealQColor(glow_color)
        col.setAlpha(int(255 * (0.05 + 0.17 * s)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        # несколько штрихов растущей толщины; видна только внутренняя половина — получается свечение внутрь
        for i in range(7):
            p.setPen(QPen(col, 1.5 + i * (2.2 + 4.0 * s)))
            p.drawPath(path)
    p.restore()

    if th["glass"]:
        s = th["glass_strength"] / 100.0
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(RealQColor(255, 255, 255, int(95 * s)), 1.0))
        p.drawPath(path)
    elif edge:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(RealQColor(0, 0, 0, 48), 1.0))
        p.drawPath(path)
