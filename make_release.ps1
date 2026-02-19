param(
    [string]$Version = "v1.0.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $root "dist\InstagramCleaner.exe"

if (-not (Test-Path $exePath)) {
    throw "EXE not found at '$exePath'. Build first using build_exe.bat"
}

$releaseBase = Join-Path $root "release"
$releaseDir = Join-Path $releaseBase $Version
$zipPath = Join-Path $releaseBase "InstagramCleaner-$Version.zip"

New-Item -Path $releaseDir -ItemType Directory -Force | Out-Null
Copy-Item $exePath (Join-Path $releaseDir "InstagramCleaner.exe") -Force
Copy-Item (Join-Path $root "README.md") $releaseDir -Force
Copy-Item (Join-Path $root "RELEASE_NOTES.md") $releaseDir -Force

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Compress-Archive -Path (Join-Path $releaseDir "*") -DestinationPath $zipPath
Write-Host "Release files created:"
Write-Host " - Folder: $releaseDir"
Write-Host " - Zip   : $zipPath"
