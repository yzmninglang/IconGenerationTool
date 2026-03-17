param(
    [switch]$SkipSync,
    [string]$Name = "IconGenerationTool",
    [string]$IconPath = "icon.ico"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot

try {
    if (-not (Test-Path $IconPath)) {
        throw "Icon file not found: $IconPath"
    }

    $env:UV_CACHE_DIR = ".uv-cache"

    if (-not $SkipSync) {
        uv sync --extra build
    }

    $pyInstallerArgs = @(
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", $Name,
        "--icon", $IconPath,
        "--add-data", "$IconPath;.",
        "src/icon_tool/app.py"
    )

    uv run pyinstaller @pyInstallerArgs

    Write-Host "Build complete: dist/$Name.exe"
}
finally {
    Pop-Location
}