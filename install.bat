@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Astro Island - установка
cd /d "%~dp0"

REM Make freshly installed tools visible in this session.
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

echo ============================================================
echo    Astro Island by ASTRO - установка
echo ============================================================
echo.

REM Read the required Python version from .python-version (fallback 3.12).
set "PYVER=3.12"
if exist ".python-version" set /p PYVER=<.python-version
if "%PYVER%"=="" set "PYVER=3.12"

REM ================= 1. uv =================
where uv >nul 2>nul
if not errorlevel 1 goto uv_ready

echo [1/3] uv не найден.
set "ans="
set /p "ans=Установить uv сейчас? [Y/n] "
if /i "%ans%"=="n" goto uv_missing

echo Ставлю uv...
where winget >nul 2>nul
if errorlevel 1 goto uv_powershell
winget install --id=astral-sh.uv -e --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
if errorlevel 1 goto uv_powershell
goto uv_refresh

:uv_powershell
echo winget не сработал - ставлю через PowerShell...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 goto uv_fail

:uv_refresh
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where uv >nul 2>nul
if errorlevel 1 goto uv_fail
echo   OK: uv установлен.

:uv_ready
for /f "delims=" %%v in ('uv --version 2^>nul') do echo [1/3] uv: %%v

REM ================= 2. Python =================
set "HAS_PY=0"
py -3 --version >nul 2>nul && set "HAS_PY=1"
python --version >nul 2>nul && set "HAS_PY=1"
if "%HAS_PY%"=="1" goto py_ready

echo [2/3] Python не найден.
set "ans="
set /p "ans=Установить Python %PYVER% через winget? [Y/n] "
if /i "%ans%"=="n" goto py_uv

where winget >nul 2>nul
if errorlevel 1 goto py_uv
winget install --id Python.Python.%PYVER% -e --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
set "PATH=%LOCALAPPDATA%\Programs\Python\Python%PYVER:.=%;%LOCALAPPDATA%\Programs\Python\Python%PYVER:.=%\Scripts;%ProgramFiles%\Python%PYVER:.=%;%ProgramFiles%\Python%PYVER:.=%\Scripts;%PATH%"
py -3 --version >nul 2>nul && set "HAS_PY=1"
python --version >nul 2>nul && set "HAS_PY=1"
if "%HAS_PY%"=="1" goto py_ready
echo Python из winget не появился в PATH.

:py_uv
set "ans="
set /p "ans=Скачать Python %PYVER% через uv? [Y/n] "
if /i "%ans%"=="n" goto py_skip
echo Ставлю Python через uv...
uv python install %PYVER%
if errorlevel 1 goto py_fail
set "HAS_PY=1"
echo   OK: Python установлен через uv.
goto py_ready

:py_skip
echo Пропускаю. uv подберёт Python сам при установке зависимостей.

:py_ready
if not "%HAS_PY%"=="1" goto py_done
for /f "delims=" %%v in ('python --version 2^>nul') do echo [2/3] %%v
:py_done

REM ================= 3. Dependencies =================
echo.
echo [3/3] Зависимости проекта.
set "ans="
set /p "ans=Установить/обновить зависимости (uv sync)? [Y/n] "
if /i "%ans%"=="n" goto deps_skip
echo Ставлю зависимости...
uv sync
if errorlevel 1 goto deps_fail
echo   OK: зависимости установлены.

:deps_skip
echo.
set "ans="
set /p "ans=Запустить Astro Island сейчас? [Y/n] "
if /i "%ans%"=="n" goto finish
uv run astro-island

:finish
echo.
echo Готово! Ручной запуск:
echo    uv run astro-island
echo    uv run astro-island-settings
echo.
pause
exit /b 0

:uv_missing
echo.
echo Без uv установить проект нельзя.
echo Поставь его вручную: https://docs.astral.sh/uv/getting-started/installation/
pause
exit /b 1

:uv_fail
echo.
echo [ОШИБКА] Не удалось установить uv.
echo Поставь его вручную: https://docs.astral.sh/uv/getting-started/installation/
pause
exit /b 1

:py_fail
echo.
echo [ОШИБКА] Не удалось скачать Python через uv.
pause
exit /b 1

:deps_fail
echo.
echo [ОШИБКА] uv sync завершился с ошибкой. Смотри сообщения выше.
pause
exit /b 1
