# 🏝️ Astro Island (by ASTRO)

[English](#english) | [Русский](#русский)

---

## English

A custom, smooth desktop Dynamic Island for Windows built with Python (PySide6).

### ✨ Features
* 🎵 **Media Player Integration** — control your music directly from the island.
* 📊 **Hardware Monitoring** — keep an eye on your system performance.
* ⏱️ **Timers & Clocks** — convenient tools right at your cursor.
* 📋 **Clipboard Manager** — quick access to your copied history.
* ⚙️ **Advanced Settings Panel** — fully customizable look, feel, and behavior.
* 🚀 **Multi-threaded & Optimized** — runs smoothly without lags or freezes.

### 🚀 Installation & Usage

#### Option A — one click (Windows)
1. Download or clone the project folder.
2. Double-click **`install.bat`**.
3. Answer the prompts (`[Y/n]`). The script:
   * checks whether **uv** is installed and installs it if needed
     (via `winget`, falling back to the official PowerShell installer);
   * checks whether **Python** is installed and offers to install it
     (via `winget`, falling back to `uv python install`);
   * runs `uv sync` to install the project dependencies;
   * optionally launches the island.
4. Afterwards, start the app any time with:
   ```bash
   uv run astro-island
   uv run astro-island-settings
   ```

#### Option B — manual (any OS)
1. Install **[Python 3.10+](https://www.python.org/downloads/)** and
   **[uv](https://docs.astral.sh/uv/getting-started/installation/)**.
2. From the project folder, install the dependencies:
   ```bash
   uv sync
   ```
3. Start the island / settings:
   ```bash
   uv run astro-island
   uv run astro-island-settings
   ```

You can also run the package as a module with `uv run python -m astro_island`.

### 🧱 Project layout
```
.
├── install.bat           # one-click Windows bootstrap (optional)
├── pyproject.toml        # project metadata, dependencies, CLI entry points
├── uv.lock               # reproducible dependency lockfile
├── src/
│   └── astro_island/     # application package (importable code)
├── assets/               # icons used by packaging / documentation
└── scripts/
    └── exe_branding.py   # maintainer-only helper (not needed to run the app)
```

### 🔄 Updates & Removal
* **How to update:** pull the new version, then run `uv sync` again.
* **How to uninstall:** there is no system-wide installer. Delete the project
  folder (and its `.venv`) to remove the program. User settings live in
  `%APPDATA%\DynamicIslandRU`.

### 🛠️ Project Status
Core features are fully functional and performance-optimized. We are constantly improving it — feel free to leave your ideas, feature requests, or bug reports in the **Issues** tab!

---

## Русский

Кастомный, плавный десктопный Dynamic Island для Windows, написанный на Python (PySide6).

### ✨ Возможности
* 🎵 **Интеграция с плеером** — управляйте музыкой прямо с островка.
* 📊 **Мониторинг системы** — следите за производительностью компьютера.
* ⏱️ **Таймеры и часы** — удобные инструменты всегда под рукой.
* 📋 **Менеджер буфера обмена** — быстрый доступ к истории скопированного текста.
* ⚙️ **Продвинутая панель настроек** — полностью настраиваемый внешний вид и поведение.
* 🚀 **Многопоточность и оптимизация** — работает плавно, без лагов и фризов.

### 🚀 Установка и использование

#### Вариант A — в один клик (Windows)
1. Скачайте или склонируйте папку проекта.
2. Дважды кликните по **`install.bat`**.
3. Отвечайте на вопросы (`[Y/n]`). Скрипт:
   * проверит, установлен ли **uv**, и при необходимости поставит его
     (через `winget`, а если не выйдет — официальным PowerShell-скриптом);
   * проверит **Python** и предложит установить его
     (через `winget`, а если не выйдет — через `uv python install`);
   * выполнит `uv sync`, чтобы поставить зависимости проекта;
   * по желанию сразу запустит остров.
4. Дальше запускайте приложение командами:
   ```bash
   uv run astro-island
   uv run astro-island-settings
   ```

#### Вариант B — вручную (любая ОС)
1. Установите **[Python 3.10+](https://www.python.org/downloads/)** и
   **[uv](https://docs.astral.sh/uv/getting-started/installation/)**.
2. В папке проекта поставьте зависимости:
   ```bash
   uv sync
   ```
3. Запустите остров / настройки:
   ```bash
   uv run astro-island
   uv run astro-island-settings
   ```

Также можно запустить пакет как модуль: `uv run python -m astro_island`.

### 🧱 Структура проекта
```
.
├── install.bat           # установка в один клик для Windows (необязательно)
├── pyproject.toml        # метаданные, зависимости и точки входа CLI
├── uv.lock               # зафиксированные версии зависимостей
├── src/
│   └── astro_island/     # пакет приложения
├── assets/               # иконки для упаковки и документации
└── scripts/
    └── exe_branding.py   # вспомогательный скрипт для сборки (для запуска не нужен)
```

### 🔄 Обновление и удаление
* **Как обновить:** скачайте новую версию и снова выполните `uv sync`.
* **Как удалить:** отдельного установщика нет. Удалите папку проекта (вместе с
  `.venv`). Настройки пользователя хранятся в `%APPDATA%\DynamicIslandRU`.

### 🛠️ Статус проекта
Основные функции полностью готовы и оптимизированы по производительности. Проект постоянно дорабатывается — смело оставляйте свои идеи, предложения или сообщения об ошибках во вкладке **Issues**!
