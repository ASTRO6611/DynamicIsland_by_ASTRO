# Downloads the bundled local AI assets into src/astro_island/ai (not stored in git):
#   * llama-server.exe + DLLs (llama.cpp release, CPU x64)
#   * model.gguf (Qwen2.5-1.5B-Instruct, Q4_K_M)
# Run: powershell -ExecutionPolicy Bypass -File scripts\fetch_ai.ps1
$ErrorActionPreference = "Continue"
Set-Location (Resolve-Path "$PSScriptRoot\..")

$dir = Join-Path $PWD "src\astro_island\ai"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$server = Join-Path $dir "llama-server.exe"
if (-not (Test-Path $server)) {
    $tag = "b12387"
    $url = "https://github.com/ggml-org/llama.cpp/releases/download/$tag/llama-$tag-bin-win-cpu-x64.zip"
    $zip = Join-Path $env:TEMP "llama-cpu-x64.zip"
    Write-Host "Downloading llama.cpp ($tag)..."
    Invoke-WebRequest $url -OutFile $zip -TimeoutSec 600
    Expand-Archive $zip -DestinationPath $dir -Force
    Remove-Item $zip -Force

    # Keep only what llama-server needs.
    $keep = @("llama-server.exe", "llama-server-impl.dll", "llama-common.dll", "llama.dll",
              "ggml.dll", "ggml-base.dll", "mtmd.dll", "libomp.dll", "LICENSE-LLVM-OpenMP")
    Get-ChildItem $dir -File | Where-Object {
        $keep -notcontains $_.Name -and $_.Name -notmatch "^ggml-cpu-.*\.dll$"
    } | Remove-Item -Force
}

$model = Join-Path $dir "model.gguf"
if (-not (Test-Path $model)) {
    $url = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
    Write-Host "Downloading Qwen2.5-1.5B-Instruct Q4_K_M (~1 GB)..."
    Invoke-WebRequest $url -OutFile $model -TimeoutSec 3600
}

Write-Host "AI assets ready: $dir"
Get-ChildItem $dir | Measure-Object Length -Sum | ForEach-Object {
    Write-Host ("Total: {0:N0} MB" -f ($_.Sum / 1MB))
}
