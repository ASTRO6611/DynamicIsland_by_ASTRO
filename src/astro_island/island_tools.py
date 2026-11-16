"""Инструменты локальной ИИ: то, что модель умеет делать на самом острове.

Модель получает OpenAI-совместимый список функций (:data:`TOOLS`) и, когда её просят
«поставь таймер на 10 минут», не рассказывает как это сделать руками, а вызывает
``set_timer``. Выполняется всё на главном потоке (см. ``AIPage._run_tool``), потому что
инструменты дёргают настоящие страницы острова — результат сразу виден в интерфейсе.

Каждый инструмент возвращает пару ``(ответ_модели, подпись_для_чата)``.
"""
import datetime as dt
import time

from PySide6.QtGui import QGuiApplication

# названия вкладок — чтобы модель могла открыть нужную
TABS = {"clock": "Часы", "timer": "Таймер", "reminders": "Напоминания", "calc": "Калькулятор",
        "ai": "ИИ", "system": "Система", "rec": "Запись", "music": "Музыка", "mixer": "Микшер",
        "clip": "Буфер", "eye": "Глазок", "shelf": "Полка"}

TOOLS = [
    {"type": "function", "function": {
        "name": "set_timer",
        "description": "Поставить таймер обратного отсчёта и сразу запустить его.",
        "parameters": {"type": "object", "properties": {
            "minutes": {"type": "number", "description": "Длительность в минутах, можно дробное: 0.5 — это 30 секунд"}},
            "required": ["minutes"]}}},
    {"type": "function", "function": {
        "name": "stop_timer",
        "description": "Остановить и сбросить таймер обратного отсчёта.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "add_reminder",
        "description": ("Создать напоминание, которое всплывёт на острове через заданное время. "
                        "Поле text — дословная цитата из запроса пользователя, без изменения слов. "
                        "Пример: запрос «напомни через 30 минут полить цветы» → text = «полить цветы», "
                        "minutes = 30."),
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string", "description": "Дословная цитата из запроса пользователя"},
            "minutes": {"type": "number", "description": "Через сколько минут напомнить"}},
            "required": ["text", "minutes"]}}},
    {"type": "function", "function": {
        "name": "calc",
        "description": ("Точно посчитать арифметическое выражение. Всегда используй этот инструмент для "
                        "любых вычислений — в уме ты ошибаешься."),
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string",
                           "description": "Выражение: 12*8, (1500-200)/3, 1500*20%"}},
            "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "get_datetime",
        "description": "Текущие дата, время и день недели на компьютере пользователя.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "Погода, которую остров показывает на вкладке «Часы».",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "media",
        "description": "Управление текущим плеером (музыка, видео).",
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["toggle", "next", "prev"],
                       "description": "toggle — пауза/продолжить, next — следующий трек, prev — предыдущий"}},
            "required": ["action"]}}},
    {"type": "function", "function": {
        "name": "set_volume",
        "description": "Общая громкость системы в процентах.",
        "parameters": {"type": "object", "properties": {
            "level": {"type": "integer", "description": "0–100"}},
            "required": ["level"]}}},
    {"type": "function", "function": {
        "name": "open_tab",
        "description": "Показать пользователю вкладку острова.",
        "parameters": {"type": "object", "properties": {
            "tab": {"type": "string", "enum": list(TABS),
                    "description": "Ключ вкладки: clock, timer, reminders, calc, ai, system, rec, music, mixer, clip, eye, shelf"}},
            "required": ["tab"]}}},
    {"type": "function", "function": {
        "name": "record",
        "description": "Запись экрана: начать или остановить.",
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["start", "stop"]}},
            "required": ["action"]}}},
    {"type": "function", "function": {
        "name": "take_screenshot",
        "description": "Сделать скриншот экрана (сохраняется в папку и копируется в буфер).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_system_info",
        "description": "Загрузка процессора, память, диск и заряд батареи.",
        "parameters": {"type": "object", "properties": {}}}},
]


def _plural(n, one, few, many):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _minutes_text(minutes):
    if minutes < 1:
        sec = int(round(minutes * 60))
        return f"{sec} {_plural(sec, 'секунда', 'секунды', 'секунд')}"
    if abs(minutes - round(minutes)) < 0.01:
        m = int(round(minutes))
        return f"{m} {_plural(m, 'минута', 'минуты', 'минут')}"
    return f"{minutes:.1f} минуты"


def _system_info():
    try:
        import psutil
    except Exception:
        return "psutil не установлен — подробностей о системе нет"
    parts = []
    try:
        parts.append(f"ЦП {psutil.cpu_percent(interval=0.15):.0f}%")
        vm = psutil.virtual_memory()
        parts.append(f"память {vm.percent:.0f}% ({vm.used / 2 ** 30:.1f} из {vm.total / 2 ** 30:.1f} ГБ)")
        du = psutil.disk_usage("C:\\")
        parts.append(f"диск C: занято {du.percent:.0f}%")
        bat = getattr(psutil, "sensors_battery", lambda: None)()
        if bat is not None:
            plug = "заряжается" if bat.power_plugged else "от батареи"
            parts.append(f"батарея {bat.percent:.0f}% ({plug})")
    except Exception as e:
        parts.append(f"ошибка чтения: {e}")
    return ", ".join(parts)


def run_tool(host, name, args):
    """Выполнить инструмент на острове. Возвращает ``(ответ_модели, подпись_для_чата)``."""
    a = args or {}

    if name == "set_timer":
        try:
            minutes = float(a.get("minutes", 5))
        except Exception:
            minutes = 5.0
        minutes = max(0.05, min(minutes, 99 * 60))
        page = host.timer_page
        page.reset()
        page.add(int(round(minutes * 60)))
        page.toggle()
        text = _minutes_text(minutes)
        return f"таймер на {text} запущен", f"Таймер на {text}"

    if name == "stop_timer":
        host.timer_page.reset()
        return "таймер сброшен", "Таймер сброшен"

    if name == "add_reminder":
        text = str(a.get("text") or "Напоминание").strip()[:120] or "Напоминание"
        try:
            minutes = max(0.05, float(a.get("minutes", 10)))
        except Exception:
            minutes = 10.0
        ts = time.time() + minutes * 60
        page = host.rem_page
        page.items.append({"text": text, "ts": ts})
        page.items.sort(key=lambda x: x["ts"])
        page.rebuild()
        when = dt.datetime.fromtimestamp(ts).strftime("%H:%M")
        return (f"напоминание «{text}» создано на {when}",
                f"Напоминание «{text}» в {when}")

    if name == "calc":
        expr = str(a.get("expression") or "").strip()
        if not expr:
            return "пустое выражение", "Калькулятор: пусто"
        try:
            from .island_modules import fmt_num, safe_eval
            value = fmt_num(safe_eval(expr))
        except Exception:
            return (f"не смог посчитать «{expr}»", f"Калькулятор: не смог «{expr}»")
        return f"{expr} = {value}", f"{expr} = {value}"

    if name == "get_datetime":
        now = dt.datetime.now()
        from . import common as C
        weekday = C.WEEKDAYS[now.weekday()]
        month = C.MONTHS_GEN[now.month - 1]
        return (f"{weekday}, {now.day} {month} {now.year} года, {now:%H:%M}",
                f"{weekday}, {now:%H:%M}")

    if name == "get_weather":
        w = host.weather
        if not getattr(w, "data", None):
            w.poll(host.cfg.get("weather_city", ""))
            return "погода ещё загружается, данных пока нет", "Погода ещё грузится"
        return (f"{w.desc_text()}, {w.temp_text()} ({w.place_text()})",
                f"Погода: {w.temp_text()}")

    if name == "media":
        action = str(a.get("action") or "toggle")
        if action not in ("toggle", "next", "prev"):
            action = "toggle"
        host.lyrics.command(action)
        return ({"toggle": "пауза/продолжить переключены", "next": "включён следующий трек",
                 "prev": "включён предыдущий трек"}[action],
                {"toggle": "Плеер: пауза/продолжить", "next": "Плеер: следующий трек",
                 "prev": "Плеер: предыдущий трек"}[action])

    if name == "set_volume":
        try:
            level = int(round(float(a.get("level", 50))))
        except Exception:
            level = 50
        level = max(0, min(100, level))
        mixer = getattr(host.pages.get("mixer"), "mixer", None)
        if mixer is None:
            return "микшер недоступен (нет pycaw)", "Громкость недоступна"
        if getattr(mixer, "master", None) is None:
            mixer.connect_master()
        if getattr(mixer, "master", None) is None:
            return (f"не удалось получить доступ к громкости: {mixer.err or 'нет устройства'}",
                    "Громкость недоступна")
        mixer.master_set(level / 100.0)
        return f"громкость {level}%", f"Громкость {level}%"

    if name == "open_tab":
        key = str(a.get("tab") or "").strip()
        if key not in host.pages:
            return (f"нет такой вкладки: {key}", f"Нет вкладки «{key}»")
        if not host.cfg["modules"].get(key, True):
            return (f"вкладка «{TABS.get(key, key)}» выключена в настройках",
                    f"Вкладка «{TABS.get(key, key)}» выключена")
        host.set_expanded(True)
        host.show_page(key)
        return f"открыта вкладка «{TABS.get(key, key)}»", f"Вкладка «{TABS.get(key, key)}»"

    if name == "record":
        rec = host.rec_page.rec
        action = str(a.get("action") or "start")
        if action == "stop":
            if rec.phase in ("starting", "recording"):
                rec.stop()
                return "запись остановлена", "Запись остановлена"
            return "запись и не шла", "Запись не идёт"
        if rec.phase != "idle":
            return "запись уже идёт", "Запись уже идёт"
        rec.start(host.cfg.get("rec_mode", "sys"))
        return "запись экрана началась", "Запись экрана"

    if name == "take_screenshot":
        host.rec_page.screenshot()
        return "скриншот сохранён и скопирован в буфер", "Скриншот"

    if name == "get_system_info":
        info = _system_info()
        return info, info

    return f"неизвестный инструмент: {name}", f"Неизвестный инструмент {name}"


def clipboard_text(limit=1500):
    """Текст из буфера обмена (для быстрых действий)."""
    return (QGuiApplication.clipboard().text() or "").strip()[:limit]


def selftest() -> int:
    """Самопроверка всех инструментов: ``DynamicIsland.exe --tools-selftest``.

    Поднимает настоящий остров (без показа окна), дёргает каждый инструмент и
    проверяет, что состояние острова действительно изменилось. Отчёт пишется в
    ``%TEMP%\\astro_tools_selftest.txt``. Возвращает число провалов.
    """
    import os
    import time

    from PySide6.QtGui import QGuiApplication

    from . import common as C

    app = C.qt_app([])
    from .island import Island

    isl = Island()
    isl.set_expanded(True)
    lines = []
    fails = 0

    def pump(seconds):
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.05)

    def check(name, cond, detail=""):
        nonlocal fails
        if not cond:
            fails += 1
        lines.append(f"{'OK  ' if cond else 'FAIL'} {name}: {detail}")

    # 1–2. таймер
    _, note = run_tool(isl, "set_timer", {"minutes": 3})
    check("set_timer", isl.timer_page.running and 170 <= isl.timer_page.remaining <= 181,
          f"running={isl.timer_page.running} осталось={isl.timer_page.remaining:.0f}с")
    _, note = run_tool(isl, "stop_timer", {})
    check("stop_timer", not isl.timer_page.running and isl.timer_page.remaining == 0, note)

    # 3. напоминание (список пользователя восстанавливаем)
    before = [dict(x) for x in isl.rem_page.items]
    text = "проверка инструментов: полить цветы"
    _, note = run_tool(isl, "add_reminder", {"text": text, "minutes": 15})
    added = [x for x in isl.rem_page.items if x["text"] == text]
    check("add_reminder", len(added) == 1 and abs((added[0]["ts"] - time.time()) / 60 - 15) < 0.5,
          "текст сохранён дословно" if added else "напоминание не создано")
    isl.rem_page.items = before
    isl.rem_page.rebuild()

    # 4. калькулятор
    _, n1 = run_tool(isl, "calc", {"expression": "(1500-200)/3"})
    _, n2 = run_tool(isl, "calc", {"expression": "1500*20%"})
    _, n3 = run_tool(isl, "calc", {"expression": "ерунда"})
    check("calc", "433" in n1 and "300" in n2 and "не смог" in n3, f"{n1} | {n2}")

    # 5. дата и время
    full, _ = run_tool(isl, "get_datetime", {})
    check("get_datetime", ":" in full and "20" in full, full)

    # 6. погода
    if not getattr(isl.weather, "data", None):
        isl.weather.poll(isl.cfg.get("weather_city", ""))
        t0 = time.time()
        while not isl.weather.data and time.time() - t0 < 20:
            pump(0.2)
    res, note = run_tool(isl, "get_weather", {})
    check("get_weather", "°" in note or "загружается" in res, note)

    # 7. плеер
    for action in ("next", "prev", "toggle"):
        _, note = run_tool(isl, "media", {"action": action})
    check("media", note.startswith("Плеер:"), note)

    # 8. громкость
    mixer = getattr(isl.pages.get("mixer"), "mixer", None)
    orig = mixer.master_get()[0] if mixer else None
    _, note = run_tool(isl, "set_volume", {"level": 30})
    vol = mixer.master_get()[0] if mixer else -1
    check("set_volume", abs(vol - 0.30) < 0.03, f"стало={vol:.2f}")
    if mixer and orig is not None:
        mixer.master_set(orig)

    # 9. вкладки
    _, note = run_tool(isl, "open_tab", {"tab": "calc"})
    ok = isl.page_key == "calc" and isl.expanded
    bad, _ = run_tool(isl, "open_tab", {"tab": "нетакой"})
    check("open_tab", ok and "нет такой вкладки" in bad, note)

    # 10. запись экрана
    rec = isl.rec_page.rec
    msgs = []
    rec.message.connect(lambda t, kind: msgs.append((kind, t)))
    run_tool(isl, "record", {"action": "start"})
    t0 = time.time()
    while rec.phase != "recording" and time.time() - t0 < 25:  # ffmpeg под нагрузкой стартует не сразу
        pump(0.25)
    started = rec.phase == "recording"
    if started:
        pump(3)
        run_tool(isl, "record", {"action": "stop"})
        t0 = time.time()
        while rec.phase != "idle" and time.time() - t0 < 60:
            pump(0.3)
        made = rec.last_path
        check("record", rec.phase == "idle" and bool(made) and os.path.exists(made),
              made or f"файла нет; последнее сообщение: {msgs[-1][1] if msgs else '-'}")
        if made and os.path.exists(made):
            try:
                os.remove(made)  # тестовая запись не нужна
            except Exception:
                pass
    else:
        check("record", False, "запись не стартовала: " + (msgs[-1][1] if msgs else "нет ffmpeg?"))
    again, _ = run_tool(isl, "record", {"action": "stop"})
    check("record повторный стоп", "не шла" in again, again)

    # 11. скриншот
    clip = QGuiApplication.clipboard().text()
    folder = C.media_dir(isl.cfg, "shot")
    seen = set(os.listdir(folder)) if folder.exists() else set()
    run_tool(isl, "take_screenshot", {})
    pump(2)
    new = (set(os.listdir(folder)) if folder.exists() else set()) - seen
    check("take_screenshot", bool(new), ", ".join(sorted(new)) or "файл не появился")
    for f in new:
        try:
            os.remove(folder / f)
        except Exception:
            pass
    if clip:
        QGuiApplication.clipboard().setText(clip)

    # 12. система
    info, _ = run_tool(isl, "get_system_info", {})
    check("get_system_info", "ЦП" in info and "память" in info, info)

    # неизвестный инструмент
    res, _ = run_tool(isl, "нет_такого", {})
    check("неизвестный инструмент", "неизвестный инструмент" in res, res)

    isl.shutdown()
    isl.close()
    app.processEvents()

    head = f"провалов: {fails} из {len(lines)}"
    report = head + "\n" + "\n".join(lines)
    try:
        path = os.path.join(os.environ.get("TEMP", "."), "astro_tools_selftest.txt")
        open(path, "w", encoding="utf-8").write(report)
    except Exception:
        pass
    try:
        print(report)
    except Exception:
        pass
    return fails

