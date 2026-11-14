# AGENTS.md — заметки для ИИ-агентов и контрибьюторов

## Что это
Dynamic Island by ASTRO — плавающий остров-оверлей для Windows на Python + PySide6:
часы, таймер, напоминания, калькулятор, система, музыка с текстами, буфер обмена,
запись экрана, микшер громкости, полка, погода и отдельное окно настроек.

## Быстрый старт
```bash
uv sync
uv run astro-island            # остров
uv run astro-island-settings   # настройки
uv run python -m astro_island  # то же, что остров
```
Пользовательские данные: `%APPDATA%\DynamicIslandRU\` (`config.json`, `shelf.json`,
`reminders.json`, `lyrics\`, `clips\`, `quit.flag`, lock-файлы).

## Структура
```
main.py                     # точка входа для Nuitka: остров / --settings
src/astro_island/
  __main__.py, cli.py       # python -m astro_island и console-scripts
  common.py                 # конфиг, темы, русские даты, запуск самого себя
  island.py                 # главный оверлей: вкладки, анимации, трей
  island_modules.py         # часы/таймер/напоминания/калькулятор/система/полка
  island_extras.py          # музыка: GSMTC + тексты LRCLIB; pip-хелперы
  island_mixer.py           # микшер приложений (pycaw/comtypes)
  island_rec.py             # запись экрана (ffmpeg + опц. PyAudioWPatch)
  island_snip.py            # скриншот и «ножницы»
  island_clip.py            # история буфера обмена
  island_downloads.py       # загрузки браузера
  island_weather.py         # погода
  settings_app.py           # окно настроек (отдельный процесс)
  theme.py, mascots.py      # оформление и персонажи
```

## Правила кода
- UI-тексты и комментарии — по-русски; имена кода — английские.
- Необязательные зависимости импортируются **лениво** внутри функций
  (`pycaw`, `comtypes`, `winsdk`/`winrt`, `imageio_ffmpeg`, `PyAudioWPatch`),
  чтобы приложение запускалось без них.
- Не ставьте пакеты «молча» из кода: используйте общий хелпер
  `island_extras.pip_install(pkgs)` — он сам чинит отсутствующий pip
  (`ensurepip`, затем `get-pip.py`) и возвращает `(ok, error)`.
- Конфиг читайте/пишите через `common.load_cfg/save_cfg`; не плодите свои пути.
- Остров — один экземпляр на пользователя (`QLockFile` в `common.CFG_DIR`),
  настройки — отдельный процесс со своим локом.
- Запуск «самого себя» (перезапуск, настройки, автозапуск) — только через
  `common.self_argv()` / `common.self_command()`: в exe это
  `DynamicIsland.exe [--settings]`, из исходников — `python -m ...`.

## Сборка exe (Nuitka)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
# результат: build\DynamicIsland.exe
```
- `--onefile`, без консоли, LTO, иконка `assets/icon.ico`, данные `icon.png`,
  бандл `imageio_ffmpeg`, `pycaw`, `comtypes`, WinRT.
- Нужен C-компилятор: MSVC (любой Python) или MinGW-w64 (только Python ≤ 3.12 —
  Nuitka это проверяет). Если MSVC нет, скрипт сам делает `.venv-build` на 3.12
  и ставит `winsdk`.
- Файл `scripts/build.ps1` держите в **ASCII**: Windows PowerShell 5.1 без BOM
  ломает парсинг на не-ASCII символах в комментариях.
- `--onefile-tempdir-spec` кэширует распаковку — иначе перезапуск и настройки
  каждый раз заново распаковывают ~200 МБ.

## Проверка изменений
Автотестов нет. Минимально:
```bash
uv run python -m compileall -q src main.py
uv run astro-island
```
Для оконных изменений — глазами: остров в покое/раскрытый, каждая вкладка,
настройки, перезапуск после смены темы.

## Частые грабли
- `sys.executable` в onefile — это exe, а не python: не вызывайте `-m ...` без
  проверки `common.is_compiled()`.
- `importlib.resources.files("astro_island")` должен работать и в exe —
  данные добавляются через `--include-data-file`.
- Не удаляйте `# noqa`/ленивые импорты «для чистоты»: они нужны для сборки и
  для запуска без опциональных пакетов.
