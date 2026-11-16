"""Векторные иконки вкладок острова — вместо цветных эмодзи.

Все значки рисуются QPainter в сетке 24×24 с одинаковым штрихом (1.8) и
скруглёнными концами, поэтому выглядят одинаково на любом DPI и не зависят
от шрифта эмодзи Windows (который рисует разноцветные картинки).

Вкладка «ИИ» — не штриховой значок: рисуется официальный логотип Qwen из
``ai_logo.png`` (лежит рядом с пакетом, попадает в exe через build.ps1). Если
файла нет, включается нарисованный запасной знак (``_ai_mark``), чтобы вкладка
не осталась пустой.
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)

import importlib.resources

GRID = 24.0
STROKE = 1.8
IDLE = "#9d9da3"
ACTIVE = "#ffffff"
ACCENT = ("#8b7cf6", "#5b3ff0")   # фиолетовый градиент фирменного знака

_cache = {}


# ─────────────────────────── вспомогательное ───────────────────────────
def _pen(color, width=STROKE):
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _logo_file():
    """Путь к пользовательскому логотипу ИИ внутри пакета, если он есть."""
    for name in ("ai_logo.png", "ai_logo.svg"):
        try:
            res = importlib.resources.files(__package__) / name
            if res.is_file():
                return str(res)
        except Exception:
            pass
    return None


# ─────────────────────────────── значки ───────────────────────────────
def _clock(p):
    p.drawEllipse(QPointF(12, 12), 8.6, 8.6)
    p.drawLine(QPointF(12, 7.1), QPointF(12, 12.4))
    p.drawLine(QPointF(12, 12.4), QPointF(15.6, 14.3))


def _timer(p):
    p.drawEllipse(QPointF(12, 13.3), 7.7, 7.7)
    p.drawLine(QPointF(12, 5.6), QPointF(12, 3.9))
    p.drawLine(QPointF(10.1, 3.9), QPointF(13.9, 3.9))
    p.drawLine(QPointF(17.8, 7.4), QPointF(18.9, 6.3))
    p.drawLine(QPointF(12, 13.3), QPointF(12, 9.2))
    p.drawLine(QPointF(12, 13.3), QPointF(15.2, 14.9))


def _reminders(p):
    body = QPainterPath()
    body.moveTo(6.4, 16.2)
    body.cubicTo(7.5, 15.2, 7.9, 14.0, 7.9, 12.0)
    body.lineTo(7.9, 10.6)
    body.cubicTo(7.9, 8.2, 9.7, 6.2, 12.0, 6.2)
    body.cubicTo(14.3, 6.2, 16.1, 8.2, 16.1, 10.6)
    body.lineTo(16.1, 12.0)
    body.cubicTo(16.1, 14.0, 16.5, 15.2, 17.6, 16.2)
    p.drawPath(body)
    p.drawLine(QPointF(5.4, 16.2), QPointF(18.6, 16.2))
    p.drawArc(QRectF(10.2, 16.9, 3.6, 3.4), 180 * 16, 180 * 16)


def _calc(p):
    p.drawRoundedRect(QRectF(5.6, 3.2, 12.8, 17.6), 3.0, 3.0)
    p.save()
    p.setBrush(QColor(p.pen().color()))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(8.4, 6.2, 7.2, 2.6), 1.1, 1.1)
    for y in (12.2, 15.2, 18.0):
        for x in (8.7, 12.0, 15.3):
            p.drawEllipse(QPointF(x, y), 1.12, 1.12)
    p.restore()


def _system(p):
    p.drawLine(QPointF(4.6, 19.2), QPointF(19.4, 19.2))
    p.drawLine(QPointF(8.2, 19.0), QPointF(8.2, 14.2))
    p.drawLine(QPointF(12.0, 19.0), QPointF(12.0, 8.6))
    p.drawLine(QPointF(15.8, 19.0), QPointF(15.8, 11.4))


def _rec(p):
    p.drawRoundedRect(QRectF(3.4, 6.6, 12.2, 10.8), 2.8, 2.8)
    lens = QPainterPath()
    lens.moveTo(16.8, 10.6)
    lens.lineTo(20.4, 8.4)
    lens.lineTo(20.4, 15.6)
    lens.lineTo(16.8, 13.4)
    lens.closeSubpath()
    p.drawPath(lens)


def _music(p):
    p.drawLine(QPointF(9.8, 16.4), QPointF(9.8, 6.9))
    p.drawLine(QPointF(17.6, 15.2), QPointF(17.6, 5.6))
    p.drawLine(QPointF(9.8, 6.9), QPointF(17.6, 5.6))
    p.save()
    p.setBrush(QColor(p.pen().color()))
    p.drawEllipse(QPointF(7.7, 17.0), 2.2, 1.8)
    p.drawEllipse(QPointF(15.5, 15.8), 2.2, 1.8)
    p.restore()


def _mixer(p):
    for x, y in ((7.6, 14.6), (12.0, 9.4), (16.4, 12.6)):
        p.drawLine(QPointF(x, 4.2), QPointF(x, 19.8))
        p.save()
        p.setBrush(QColor(p.pen().color()))
        p.drawEllipse(QPointF(x, y), 1.95, 1.95)
        p.restore()


def _clip(p):
    p.drawRoundedRect(QRectF(5.8, 4.6, 12.4, 16.0), 3.0, 3.0)
    p.drawRoundedRect(QRectF(9.4, 2.7, 5.2, 3.4), 1.7, 1.7)
    p.drawLine(QPointF(8.9, 11.2), QPointF(15.1, 11.2))
    p.drawLine(QPointF(8.9, 14.8), QPointF(13.1, 14.8))


def _eye(p):
    path = QPainterPath()
    path.moveTo(3.4, 12.0)
    path.cubicTo(5.9, 7.8, 8.9, 6.3, 12.0, 6.3)
    path.cubicTo(15.1, 6.3, 18.1, 7.8, 20.6, 12.0)
    path.cubicTo(18.1, 16.2, 15.1, 17.7, 12.0, 17.7)
    path.cubicTo(8.9, 17.7, 5.9, 16.2, 3.4, 12.0)
    p.drawPath(path)
    p.drawEllipse(QPointF(12, 12), 2.9, 2.9)


def _shelf(p):
    path = QPainterPath()
    path.moveTo(3.8, 17.6)
    path.lineTo(3.8, 7.8)
    path.cubicTo(3.8, 6.7, 4.6, 6.0, 5.6, 6.0)
    path.lineTo(9.0, 6.0)
    path.lineTo(10.7, 8.4)
    path.lineTo(18.4, 8.4)
    path.cubicTo(19.4, 8.4, 20.2, 9.1, 20.2, 10.2)
    path.lineTo(20.2, 17.6)
    path.cubicTo(20.2, 18.6, 19.4, 19.3, 18.4, 19.3)
    path.lineTo(5.6, 19.3)
    path.cubicTo(4.6, 19.3, 3.8, 18.6, 3.8, 17.6)
    p.drawPath(path)


def _gear(p):
    pts = []
    for i in range(16):
        ang = i * math.pi / 8 - math.pi / 2
        r = 8.4 if i % 2 == 0 else 6.3
        pts.append(QPointF(12 + r * math.cos(ang), 12 + r * math.sin(ang)))
    cog = QPainterPath()
    cog.moveTo(pts[0])
    for q in pts[1:]:
        cog.lineTo(q)
    cog.closeSubpath()
    p.drawPath(cog)
    p.drawEllipse(QPointF(12, 12), 3.0, 3.0)


_DRAW = {"clock": _clock, "timer": _timer, "reminders": _reminders, "calc": _calc,
         "system": _system, "rec": _rec, "music": _music, "mixer": _mixer,
         "clip": _clip, "eye": _eye, "shelf": _shelf, "gear": _gear}


# ─────────────────────────────── отрисовка ───────────────────────────────
def _ratio():
    try:
        return max(1.5, float(QGuiApplication.primaryScreen().devicePixelRatio()))
    except Exception:
        return 2.0


def _ai_mark(p, color):
    """Запасной знак ИИ, если логотипа рядом нет (обычно рисуется ``ai_logo.png``)."""
    alpha = 1.0 if color is None else max(0.55, color.alphaF())
    c1, c2 = QColor(ACCENT[0]), QColor(ACCENT[1])
    c1.setAlphaF(alpha)
    c2.setAlphaF(alpha)

    badge = QPainterPath()
    badge.moveTo(12.0, 2.1)
    badge.lineTo(20.2, 6.9)
    badge.lineTo(20.2, 17.1)
    badge.lineTo(12.0, 21.9)
    badge.lineTo(3.8, 17.1)
    badge.lineTo(3.8, 6.9)
    badge.closeSubpath()

    grad = QLinearGradient(QPointF(19, 3), QPointF(6, 21))
    grad.setColorAt(0.0, c1)
    grad.setColorAt(1.0, c2)

    p.save()
    # обводка тем же градиентом со скруглёнными стыками — углы бейджа получаются мягкими
    outline = QPen(grad, 1.9)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    outline.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(outline)
    p.setBrush(grad)
    p.drawPath(badge)

    # белая «A»-лента: две стойки и перекладина
    pen = QPen(QColor(255, 255, 255, int(255 * alpha)), 2.45)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    a = QPainterPath()
    a.moveTo(7.5, 17.4)
    a.lineTo(12.0, 7.4)
    a.lineTo(16.5, 17.4)
    p.drawPath(a)
    p.drawLine(QPointF(9.6, 13.6), QPointF(14.4, 13.6))
    p.restore()


def pixmap(key, size=20, active=False):
    """Готовая картинка значка в нужном размере (с учётом DPI экрана)."""
    ratio = _ratio()
    px = max(1, int(round(size * ratio)))
    if key == "ai":
        logo = _logo_file()
        if logo:
            pm = QIcon(logo).pixmap(px, px)
            if not pm.isNull():
                pm.setDevicePixelRatio(ratio)
                return pm
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.scale(px / GRID, px / GRID)
    if key == "ai":
        _ai_mark(p, QColor(255, 255, 255, 210) if not active else QColor(255, 255, 255))
    else:
        p.setPen(_pen(ACTIVE if active else IDLE))
        _DRAW[key](p)
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def icon(key, size=20, active=False):
    """QIcon для кнопки вкладки (кэшируется по ключу/размеру/состоянию)."""
    ck = (key, int(size), bool(active))
    ic = _cache.get(ck)
    if ic is None:
        ic = QIcon(pixmap(key, size, active))
        _cache[ck] = ic
    return ic


def clear_cache():
    """Сбросить кэш (после смены темы или появления логотипа)."""
    _cache.clear()
