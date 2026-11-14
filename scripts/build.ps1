# Build Dynamic Island into a single exe (Nuitka onefile).
# Run from the project root:  powershell -ExecutionPolicy Bypass -File scripts\build.ps1
# Result:                     build\DynamicIsland.exe
#
# Compiler:
#   * MSVC (Visual Studio Build Tools) - works with any Python, uses .venv;
#   * MinGW-w64 (gcc) - Nuitka supports it only up to Python 3.12, so a separate
#     .venv-build environment is prepared automatically when only gcc is found.
# Note: "Continue" instead of "Stop" - uv/nuitka write normal progress to stderr,
# and PowerShell 5.1 turns that into a terminating NativeCommandError.
$ErrorActionPreference = "Continue"
Set-Location (Resolve-Path "$PSScriptRoot\..")

$py = Join-Path $PWD ".venv\Scripts\python.exe"
$nuitkaArgs = @()

if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    # MinGW mode: Nuitka can download its own gcc if none is on PATH.
    $ver = & $py -c "import sys; print('%d.%d' % sys.version_info[:2])"
    if ([version]$ver -ge [version]"3.13") {
        Write-Host "MinGW does not support Python $ver - building with Python 3.12 instead." -ForegroundColor Yellow
        $py = Join-Path $PWD ".venv-build\Scripts\python.exe"
        if (-not (Test-Path $py)) {
            uv python install 3.12
            uv venv .venv-build --python 3.12
        }
        # winsdk provides WinRT on Python 3.12 (3.13+ uses the winrt-* packages).
        uv pip install --python $py nuitka pyside6 pillow psutil imageio-ffmpeg pycaw comtypes winsdk
    }
    $nuitkaArgs += "--mingw64"
}

# Nuitka has to see the package from src/.
$env:PYTHONPATH = (Join-Path $PWD "src")

# WinRT: winsdk on Python <= 3.12, separate winrt-* modules on 3.13+.
$pyMinor = & $py -c "import sys; print(sys.version_info[1])"
if ($pyMinor -ge 13) {
    $nuitkaArgs += @(
        "--include-module=winrt.runtime",
        "--include-module=winrt.system",
        "--include-module=winrt.windows.foundation",
        "--include-module=winrt.windows.foundation.collections",
        "--include-module=winrt.windows.media.control",
        "--include-module=winrt.windows.storage.streams"
    )
} else {
    $nuitkaArgs += "--include-package=winsdk"
}

& $py -m nuitka @nuitkaArgs `
    --standalone `
    --onefile `
    --onefile-tempdir-spec="{CACHE_DIR}/ASTRO/DynamicIsland/{VERSION}" `
    --assume-yes-for-downloads `
    --remove-output `
    --windows-console-mode=disable `
    --python-flag=-OO `
    --lto=yes `
    --noinclude-dlls="libpython3.*" `
    --nofollow-import-to=tkinter,unittest,pytest,setuptools `
    --enable-plugin=pyside6 `
    --include-package=astro_island `
    --include-package=pycaw `
    --include-package=comtypes `
    --include-package-data=imageio_ffmpeg `
    --include-data-file=src/astro_island/icon.png=astro_island/icon.png `
    --windows-icon-from-ico=assets/icon.ico `
    --windows-company-name=ASTRO `
    --windows-product-name="Dynamic Island" `
    --windows-file-description="Dynamic Island by ASTRO" `
    --windows-file-version=1.0.0 `
    --windows-product-version=1.0.0 `
    --output-dir=build `
    --output-filename=DynamicIsland.exe `
    main.py

exit $LASTEXITCODE
