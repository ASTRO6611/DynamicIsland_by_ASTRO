"""Загрузки в браузере: остров показывает, что что-то скачивается, и сообщает, когда готово.

Как это работает. Пока браузер качает файл, он держит его в папке загрузок под временным именем:
  • Chrome, Edge, Brave, Vivaldi, Яндекс.Браузер, Opera — «имя.ext.crdownload» (у Opera бывает «.opdownload»);
  • Firefox — «имя.ext.part».
Раз в секунду смотрим эту папку: файл растёт — значит, идёт загрузка. Когда временный файл пропал
и появился готовый — загрузка завершена; если готового нет — её отменили, и мы молчим.

Плюсы: работает с любым браузером, ничего не нужно ставить в браузер. Минус: общий размер файла
неизвестен, поэтому показываем скорость и сколько уже скачано, а не проценты.
"""
import os
import threading
import time
from pathlib import Path

TEMP_EXT = (".crdownload", ".part", ".opdownload", ".download", ".partial")
GROW_WINDOW = 8.0     # файл считается качающимся, если рос за последние N секунд
FRESH_WINDOW = 6.0    # впервые замеченный файл берём, только если его трогали за последние N секунд
DONE_SHOW = 6.0       # сколько секунд держать сообщение «готово»

COLOR_BUSY = "#0a84ff"
COLOR_DONE = "#30d158"


def default_downloads_dir() -> Path:
    """Системная «Загрузки» (она может быть перенесена на другой диск), иначе ~/Downloads."""
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            try:
                val, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            finally:
                winreg.CloseKey(key)
            return Path(os.path.expandvars(val))
        except Exception:
            pass
    return Path.home() / "Downloads"


def fmt_size(n: float) -> str:
    n = float(n)
    for unit, step in (("Б", 1024), ("КБ", 1024), ("МБ", 1024), ("ГБ", 1024)):
        if n < step or unit == "ГБ":
            return f"{n:.0f} {unit}" if (unit in ("Б", "КБ") or n >= 100) else f"{n:.1f} {unit}"
        n /= step
    return f"{n:.1f} ГБ"


def fmt_speed(bps: float) -> str:
    return fmt_size(bps) + "/с"


def _short(name: str, limit: int = 18) -> str:
    return name if len(name) <= limit else name[:limit - 1] + "…"


class DownloadWatcher:
    """Фоновый поток: следит за папкой загрузок. Остров спрашивает у него activity() при отрисовке."""

    def __init__(self):
        self._lock = threading.Lock()
        self._enabled = False
        self._dir = None
        self._files = {}     # путь → {name, size, t, speed, last_grow}
        self._done = []      # (имя готового файла, момент завершения)
        self._stop = threading.Event()
        self._thread = None

    # ---- управление
    def configure(self, enabled: bool, custom_dir: str = ""):
        d = Path(custom_dir) if str(custom_dir or "").strip() else default_downloads_dir()
        with self._lock:
            if enabled != self._enabled or d != self._dir:
                self._files.clear()
                self._done.clear()
            self._enabled, self._dir = bool(enabled), d
        if enabled and (self._thread is None or not self._thread.is_alive()):
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="downloads-watch", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    def folder(self) -> Path:
        with self._lock:
            return self._dir or default_downloads_dir()

    # ---- поток
    def _loop(self):
        while not self._stop.is_set():
            with self._lock:
                enabled, d = self._enabled, self._dir
            if enabled and d is not None:
                try:
                    self._scan(d)
                except Exception:
                    pass   # папка исчезла / доступ закрыт — просто попробуем в следующую секунду
            self._stop.wait(1.0)

    def _scan(self, d: Path):
        now, mono = time.time(), time.monotonic()
        seen = {}
        try:
            with os.scandir(d) as it:
                for e in it:
                    if not e.name.lower().endswith(TEMP_EXT):
                        continue
                    try:
                        st = e.stat()
                    except OSError:
                        continue
                    seen[e.path] = (e.name, st.st_size, st.st_mtime)
        except OSError:
            with self._lock:
                self._files.clear()
            return

        gone = []
        with self._lock:
            for path, (name, size, mtime) in seen.items():
                f = self._files.get(path)
                if f is None:
                    if now - mtime > FRESH_WINDOW:
                        continue   # старый недокачанный файл, давно лежит без движения
                    self._files[path] = {"name": name, "size": size, "t": mono, "speed": 0.0, "last_grow": mono}
                    continue
                dt = max(0.001, mono - f["t"])
                if size > f["size"]:
                    inst = (size - f["size"]) / dt
                    f["speed"] = inst if f["speed"] <= 0 else f["speed"] * 0.6 + inst * 0.4
                    f["last_grow"] = mono
                else:
                    f["speed"] *= 0.5
                f["size"], f["t"] = size, mono
            for path in [p for p in self._files if p not in seen]:
                gone.append((path, self._files.pop(path)))

        for path, f in gone:
            if mono - f["last_grow"] > GROW_WINDOW + 4:
                continue   # он и так давно стоял — не считаем это завершением
            final = self._final_name(d, path, f["size"], now)
            if final:
                with self._lock:
                    self._done.append((final, time.monotonic()))

    @staticmethod
    def _final_name(d: Path, temp_path: str, last_size: int, now: float):
        """Имя готового файла, если загрузка завершилась (а не была отменена), иначе None."""
        low = temp_path.lower()
        for ext in TEMP_EXT:
            if low.endswith(ext):
                base = temp_path[:-len(ext)]
                if os.path.isfile(base):
                    return os.path.basename(base)
                break
        # Chrome качает под именем «Unconfirmed 123.crdownload» и переименовывает в конце —
        # ищем свежий файл подходящего размера
        best = None
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.name.lower().endswith(TEMP_EXT) or not e.is_file():
                        continue
                    st = e.stat()
                    if now - st.st_mtime <= 15 and st.st_size >= last_size * 0.9 > 0:
                        if best is None or st.st_mtime > best[0]:
                            best = (st.st_mtime, e.name)
        except OSError:
            return None
        return best[1] if best else None

    # ---- для острова
    def activity(self):
        """(текст, цвет, вид, доля) — как у таймера в Island._activity(), либо None.
        Вид: 'dl' — идёт загрузка, 'dl_done' — только что завершилась."""
        mono = time.monotonic()
        with self._lock:
            if not self._enabled:
                return None
            act = [f for f in self._files.values() if mono - f["last_grow"] <= GROW_WINDOW]
            self._done = [x for x in self._done if mono - x[1] <= DONE_SHOW]
            done = list(self._done)
        if act:
            speed = sum(f["speed"] for f in act)
            total = sum(f["size"] for f in act)
            info = fmt_speed(speed) if speed >= 1024 else fmt_size(total)
            text = info if len(act) == 1 else f"{len(act)} · {info}"
            return (text, COLOR_BUSY, "dl", 0.0)
        if done:
            return (_short(done[-1][0]), COLOR_DONE, "dl_done", 0.0)
        return None
