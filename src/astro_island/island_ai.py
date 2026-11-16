"""Локальная ИИ на острове: чат с моделью, которая лежит рядом с приложением.

Работает полностью офлайн: поднимаем встроенный ``llama-server`` (llama.cpp) с GGUF-моделью
из пакета ``astro_island/ai`` и общаемся с ним по OpenAI-совместимому API на localhost.
Сервер стартует лениво — только когда открыли вкладку «ИИ», и гаснет после простоя.
"""
import html
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser,
                               QVBoxLayout, QWidget)

from . import island_tools
from .island_modules import INPUT_QSS, btn_style

NOWIN = 0x08000000 if os.name == "nt" else 0
SERVER_EXE = "llama-server.exe"
MODEL_FILE = "model.gguf"
SYSTEM = ("Ты — локальный ИИ-ассистент на рабочем столе Windows (Dynamic Island). "
          "Отвечай по-русски, кратко и по делу, без лишних вступлений, только кириллицей. "
          "У тебя есть инструменты острова: таймер, напоминания, погода, плеер, громкость, "
          "вкладки, запись экрана, скриншот, сведения о системе, калькулятор. Если пользователь "
          "просит что-то сделать — сразу вызывай подходящий инструмент. Никогда не повторяй "
          "запрос пользователя и не объясняй, как сделать это вручную. Вызовы инструментов не "
          "выводи текстом — только настоящие вызовы. Примеры: «открой вкладку "
          "система» → open_tab(tab=\"system\"), «таймер на 10 минут» → set_timer(minutes=10), "
          "«какая погода» → get_weather(). Считать в уме не пытайся: для любых вычислений есть "
          "calc. Время и дату не выдумывай — для них есть get_datetime. "
          "Текст напоминания передавай дословно. После вызова коротко подтверди результат.")
IDLE_STOP_SEC = 8 * 60          # столько держим модель в памяти после закрытия вкладки
MAX_HISTORY = 4                 # сколько последних реплик отправляем модели (короче — точнее выбор инструментов)
MAX_INPUT = 3000                # символов из буфера/ввода
MAX_TOOL_ROUNDS = 3             # сколько раз подряд модель может звать инструменты
TOOL_TIMEOUT = 25               # секунд на выполнение одного инструмента


def ai_dir():
    """Папка с llama-server.exe и model.gguf (в исходниках и в собранном exe)."""
    here = Path(__file__).resolve().parent
    candidates = [here / "ai"]
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        # в onefile __file__ лежит в распакованной папке, рядом же и данные
        candidates.append(Path(sys.argv[0]).resolve().parent / "ai")
    for d in candidates:
        if (d / SERVER_EXE).is_file() and (d / MODEL_FILE).is_file():
            return d
    return None


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


_JOBS = []  # держим job-хэндлы открытыми: они закрываются вместе с процессом


def _bind_to_job(proc):
    """Привязывает сервер к job-объекту с KILL_ON_JOB_CLOSE.

    Если остров завершится аварийно (диспетчер задач, падение), llama-server
    не останется висеть в памяти на полтора гигабайта.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits),
                        ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return
        info = ExtendedLimits()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            k32.CloseHandle(job)
            return
        if not k32.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc._handle))):
            k32.CloseHandle(job)
            return
        _JOBS.append(job)
    except Exception:
        pass


def selftest():
    """Служебная проверка собранного exe: ``ASTRO_AI_SELFTEST=1``.

    Поднимает встроенный llama-server, задаёт простой вопрос и пишет отчёт в
    ``%TEMP%\\astro_ai_selftest.txt`` — в exe без консоли print никуда не идёт.
    """
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance() or QCoreApplication([])
    ai = LocalAI()
    parts, done = [], []
    ai.chunk.connect(parts.append)
    ai.finished.connect(done.append)
    ai.start()
    stop_at = time.monotonic() + 240
    while ai.state == "starting" and time.monotonic() < stop_at:
        app.processEvents()
        time.sleep(0.1)
    if ai.state == "ready":
        ai.ask([{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Сколько будет 2+2? Ответь одним числом."}])
        while not done and time.monotonic() < stop_at:
            app.processEvents()
            time.sleep(0.05)
    ai.shutdown()
    report = (f"state={ai.state} detail={ai.detail} dir={ai_dir()}\n"
              f"error={done[0] if done else 'timeout'}\n"
              f"answer={''.join(parts)}\n")
    try:
        (Path(os.environ.get("TEMP") or ".") / "astro_ai_selftest.txt").write_text(report, encoding="utf-8")
    except Exception:
        pass


class ToolRequest:
    """Просьба модели выполнить инструмент: из фонового потока — на главный.

    Фоновый поток ждёт ``done``, главный выполняет действие на острове и кладёт
    результат в ``result`` (это то, что увидит модель) и ``note`` (подпись в чате).
    """

    def __init__(self, name, args):
        self.name, self.args = name, args
        self.result = ""
        self.note = ""
        self.done = threading.Event()


class LocalAI(QObject):
    """Жизненный цикл llama-server и потоковый чат с ним."""
    status_changed = Signal(str)   # idle | starting | ready | error
    chunk = Signal(str)
    finished = Signal(str)         # "" — нормально, "stopped" — остановили, иначе текст ошибки
    tool_request = Signal(object)  # ToolRequest — выполняется на главном потоке (AIPage)

    def __init__(self):
        super().__init__()
        self.state = "idle"
        self.detail = ""
        self.port = 0
        self.proc = None
        self._busy = False
        self._cancel = threading.Event()
        self._boot_lock = threading.Lock()

    # ---- состояние
    def _set(self, state, detail=""):
        self.state, self.detail = state, detail
        self.status_changed.emit(state)

    @property
    def busy(self):
        return self._busy

    # ---- запуск сервера
    def start(self):
        if self.state in ("starting", "ready"):
            return
        self._set("starting")
        threading.Thread(target=self._boot, daemon=True).start()

    def _boot(self):
        with self._boot_lock:
            if self.state == "ready" and self.proc and self.proc.poll() is None:
                return
            d = ai_dir()
            if d is None:
                self._set("error", "не найдены llama-server.exe / model.gguf "
                                   "(возможно, антивирус удалил их из папки распаковки)")
                return
            if self.proc and self.proc.poll() is None:
                self._kill_proc()
            self.port = _free_port()
            threads = max(2, min(8, (os.cpu_count() or 4) // 2))
            cmd = [str(d / SERVER_EXE), "-m", str(d / MODEL_FILE), "-c", "2048",
                   "-t", str(threads), "--host", "127.0.0.1", "--port", str(self.port), "-lv", "1",
                   "--jinja"]  # шаблон чата из модели — без него llama.cpp не разбирает вызовы инструментов
            try:
                self.proc = subprocess.Popen(cmd, cwd=str(d), stdin=subprocess.DEVNULL,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                             creationflags=NOWIN)
            except Exception as e:
                self._set("error", f"{type(e).__name__}: {e}")
                return
            _bind_to_job(self.proc)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if self.proc.poll() is not None:
                    self._set("error", "llama-server завершился при запуске")
                    return
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as r:
                        if json.loads(r.read().decode("utf-8")).get("status") == "ok":
                            self._set("ready")
                            return
                except Exception:
                    pass
                time.sleep(0.4)
            self._kill_proc()
            self._set("error", "модель не загрузилась за 2 минуты")

    def _kill_proc(self):
        p, self.proc = self.proc, None
        if p is not None and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    def stop_server(self):
        if self._busy:
            return
        self._kill_proc()
        if self.state != "error":
            self._set("idle")

    def shutdown(self):
        self._cancel.set()
        self._kill_proc()

    # ---- чат
    def cancel(self):
        self._cancel.set()

    def ask(self, messages, tools=None):
        if self._busy or self.state != "ready":
            return False
        self._busy = True
        self._cancel.clear()
        threading.Thread(target=self._ask, args=(messages, tools), daemon=True).start()
        return True

    # ---- разговор с моделью
    def _ask(self, messages, tools=None):
        err = ""
        try:
            msgs = list(messages)
            rounds = 0
            while True:
                # последний круг идёт без инструментов — чтобы модель точно ответила словами
                use = tools if (tools and rounds < MAX_TOOL_ROUNDS) else None
                content, calls = self._stream(msgs, use)
                if not calls or self._cancel.is_set():
                    break
                rounds += 1
                msgs.append({"role": "assistant", "content": content, "tool_calls": [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": c["args"] or "{}"}} for c in calls]})
                for c in calls:
                    msgs.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"],
                                 "content": self._call_tool(c)})
        except Exception as e:
            if not self._cancel.is_set():
                err = f"{type(e).__name__}: {e}"
        finally:
            self._busy = False
            self.finished.emit("stopped" if self._cancel.is_set() else err)

    def _stream(self, messages, tools=None):
        """Один запрос к серверу. Возвращает (текст, список вызовов инструментов)."""
        body = {"messages": messages, "stream": True, "temperature": 0.3,
                "max_tokens": 512, "repeat_penalty": 1.1}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions",
                                     data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        text, calls = "", {}
        try:
            resp = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            # старые сборки llama.cpp не знают про tools — тогда просто обычный чат
            if tools and e.code == 400:
                return self._stream(messages, None)
            raise
        with resp:
            for raw in resp:
                if self._cancel.is_set():
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0].get("delta", {})
                except Exception:
                    continue
                piece = delta.get("content") or ""
                if piece:
                    text += piece
                    self.chunk.emit(piece)
                for tc in delta.get("tool_calls") or []:
                    slot = calls.setdefault(tc.get("index", 0),
                                            {"id": "", "name": "", "args": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["args"] += fn["arguments"]
        out = [calls[i] for i in sorted(calls) if calls[i]["name"]]
        for i, c in enumerate(out):
            c["id"] = c["id"] or f"call_{i}"
        return text, out

    def _call_tool(self, call):
        """Просим главный поток выполнить инструмент и ждём результат."""
        try:
            args = json.loads(call["args"] or "{}")
            if not isinstance(args, dict):
                args = {}
        except Exception:
            args = {}
        req = ToolRequest(call["name"], args)
        self.tool_request.emit(req)
        if not req.done.wait(TOOL_TIMEOUT):
            return "инструмент не ответил вовремя"
        return req.result or "готово"


class AIPage(QWidget):
    """Вкладка «ИИ»: чат и быстрые действия с текстом из буфера обмена."""

    def __init__(self):
        super().__init__()
        self.ai = LocalAI()
        self.ai.status_changed.connect(self._on_status)
        self.ai.chunk.connect(self._on_chunk)
        self.ai.finished.connect(self._on_finished)
        self.ai.tool_request.connect(self._run_tool)
        self.host = None       # Island подставляет себя: инструменты дёргают его вкладки
        self.history = []      # [{"role": ..., "content": ...}] — без system
        self.transcript = []   # [(role, text)] — что показываем
        self._live = ""        # текущий потоковый ответ
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(self.ai.stop_server)
        self._build_ui()

    # ---- интерфейс
    def _build_ui(self):
        self.setStyleSheet(INPUT_QSS)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.status = QLabel("ИИ: выключен")
        self.status.setStyleSheet("color:#8e8e93;font-size:12px;font-weight:600")
        top.addWidget(self.status)
        top.addStretch()
        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.setStyleSheet(btn_style("#1c1c1e", "#d0d0d5", "#2c2c2e", 10, 12))
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_btn.clicked.connect(self.clear_chat)
        top.addWidget(self.clear_btn)
        lay.addLayout(top)

        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(False)
        self.chat.setStyleSheet("QTextBrowser{background:#101012;border:1px solid #2c2c2e;border-radius:12px;"
                                "padding:8px;color:#fff;font-size:13px;selection-background-color:#3a6df0}")
        lay.addWidget(self.chat, 1)

        quick = QHBoxLayout()
        quick.setSpacing(6)
        for title, kind in (("Перевести", "translate"), ("Объяснить", "explain"), ("Суммировать", "summarize")):
            b = QPushButton(title)
            b.setStyleSheet(btn_style("#1c1c1e", "#d0d0d5", "#2c2c2e", 10, 12))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, k=kind: self.quick_action(k))
            quick.addWidget(b)
        quick.addStretch()
        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setStyleSheet(btn_style("#3a1d1f", "#ff9f9f", "#4a2326", 10, 12))
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stop_btn.clicked.connect(self.ai.cancel)
        self.stop_btn.setEnabled(False)
        quick.addWidget(self.stop_btn)
        lay.addLayout(quick)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Спросите или поручите: «таймер на 10 минут»…")
        self.input.setFixedHeight(34)
        self.input.returnPressed.connect(self.send)
        row.addWidget(self.input, 1)
        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedSize(44, 34)
        self.send_btn.setStyleSheet(btn_style("#0a84ff", "#ffffff", "#3d9bff", 12, 16))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.send_btn.clicked.connect(self.send)
        row.addWidget(self.send_btn)
        lay.addLayout(row)

        self._render()

    # ---- показ страницы: ленивый старт и остановка по простою
    def showEvent(self, _):
        self._idle.stop()
        if self.ai.state in ("idle", "error"):
            self.ai.start()

    def hideEvent(self, _):
        if not self.ai.busy:
            self._idle.start(IDLE_STOP_SEC * 1000)

    # ---- статус
    def _on_status(self, state):
        text = {"idle": "ИИ: выключен", "starting": "ИИ: загружаю модель…",
                "ready": "ИИ: готов", "error": "ИИ: ошибка"}.get(state, state)
        color = {"ready": "#30d158", "starting": "#ff9f0a", "error": "#ff453a"}.get(state, "#8e8e93")
        self.status.setText(text + (f" — {self.ai.detail}" if state == "error" and self.ai.detail else ""))
        self.status.setStyleSheet(f"color:{color};font-size:12px;font-weight:600")
        self.input.setEnabled(state == "ready")

    # ---- отправка
    def _clipboard(self):
        return (QGuiApplication.clipboard().text() or "").strip()[:MAX_INPUT]

    def quick_action(self, kind):
        text = self._clipboard()
        if not text:
            self._note("В буфере обмена нет текста.")
            return
        prompts = {
            "translate": "Переведи текст на русский (если он уже на русском — на английский), сохрани структуру:\n\n",
            "explain": "Объясни простыми словами, что это значит:\n\n",
            "summarize": "Кратко перескажи главное (3–5 пунктов):\n\n",
        }
        self.input.setText(prompts[kind] + text)
        self.send()

    def send(self):
        text = self.input.text().strip()
        if not text or self.ai.state != "ready" or self.ai.busy:
            return
        self.input.clear()
        self.transcript.append(("user", text))
        self.history.append({"role": "user", "content": text[:MAX_INPUT]})
        self._live = ""
        self._render(streaming=True)
        msgs = [{"role": "system", "content": SYSTEM}] + self.history[-MAX_HISTORY:]
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        if not self.ai.ask(msgs, island_tools.TOOLS):
            self._on_finished("busy")

    # ---- инструменты
    def _run_tool(self, req):
        """Выполняется на главном потоке: остров реально ставит таймер, включает музыку и т.д."""
        note = ""
        try:
            if self.host is None:
                req.result, note = "остров недоступен", "Инструмент недоступен"
            else:
                req.result, note = island_tools.run_tool(self.host, req.name, req.args)
        except Exception as e:
            req.result = note = f"ошибка инструмента: {e}"
        finally:
            req.done.set()
        if note:
            self.transcript.append(("tool", note))
            self._render(streaming=True)

    def _on_chunk(self, piece):
        self._live += piece
        self._render(streaming=True)

    def _on_finished(self, err):
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self._live:
            self.transcript.append(("ai", self._live))
            self.history.append({"role": "assistant", "content": self._live})
            self.history = self.history[-MAX_HISTORY * 2:]
            self._live = ""
        if err == "stopped":
            self._note("Остановлено.")
        elif err == "busy":
            self._note("Модель ещё загружается — подождите пару секунд.")
        elif err:
            self._note(f"Ошибка: {err}")
        self._render()

    # ---- отрисовка
    def _note(self, text):
        self.transcript.append(("note", text))
        self._render()

    def clear_chat(self):
        self.history.clear()
        self.transcript.clear()
        self._live = ""
        self._render()

    def _render(self, streaming=False):
        parts = []
        for role, text in self.transcript:
            body = html.escape(text).replace("\n", "<br>")
            if role == "user":
                parts.append(f'<p style="margin:3px 0"><b style="color:#8ab4ff">Вы:</b> {body}</p>')
            elif role == "ai":
                parts.append(f'<p style="margin:3px 0"><b style="color:#c9c9cf">ИИ:</b> {body}</p>')
            elif role == "tool":
                parts.append(f'<p style="margin:3px 0;color:#8e8e93">▸ {body}</p>')
            else:
                parts.append(f'<p style="margin:3px 0;color:#8e8e93">{body}</p>')
        if streaming:
            live = html.escape(self._live).replace("\n", "<br>")
            if live:
                parts.append(f'<p style="margin:3px 0"><b style="color:#c9c9cf">ИИ:</b> {live}▌</p>')
            elif not parts:
                parts.append('<p style="margin:3px 0;color:#8e8e93">Думаю…</p>')
        if not parts:
            parts.append('<p style="margin:3px 0;color:#8e8e93">Локальная модель готова. Можно спрашивать '
                         'и поручать: «поставь таймер на 10 минут», «включи следующий трек», '
                         '«сделай громкость 30%», «напомни через час позвонить маме».</p>')
        self.chat.setHtml("".join(parts))
        sb = self.chat.verticalScrollBar()
        sb.setValue(sb.maximum())

    def shutdown(self):
        self.ai.shutdown()
