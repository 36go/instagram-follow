param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,
    [string]$Version = "v1.0.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $root "dist\InstagramCleaner.exe"
$notesPath = Join-Path $root "RELEASE_NOTES.md"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is not installed. Install it first to publish a GitHub release."
}

if (-not (Test-Path $exePath)) {
    throw "EXE not found at '$exePath'. Build first."
}

gh release create $Version $exePath --repo $Repo --title $Version --notes-file $notesPath
Write-Host "GitHub release '$Version' created for '$Repo'."
