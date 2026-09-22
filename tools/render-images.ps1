<#
.SYNOPSIS
  Renders the OG/OpenGraph and icon PNGs (and favicon.ico) from the self-contained
  HTML cards in src/og/ using headless Chrome. No Node, no external image libraries.

.USAGE
  From the project root, in PowerShell:
    powershell -ExecutionPolicy Bypass -File tools/render-images.ps1

  Produces:
    src/assets/img/og-image.png    1200x630  (from src/og/og-card.html)
    src/static/icon-512.png         512x512  (from src/og/icon-card.html)
    src/static/apple-touch-icon.png 180x180  (from src/og/icon-card.html)
    src/static/favicon-32.png        32x32   (from src/og/icon-card.html)
    src/static/favicon.ico           32x32   (built from favicon-32.png by tools/make_favicon.py)
#>

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Get-Item "$PSScriptRoot\..").FullName }

function Find-Chrome {
    $candidates = @(
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    $cmd = Get-Command "chrome.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$chrome = Find-Chrome
if (-not $chrome) {
    Write-Host "ERROR: Could not find chrome.exe under 'C:/Program Files/Google/Chrome/Application/' or 'C:/Program Files (x86)/Google/Chrome/Application/', and it is not on PATH." -ForegroundColor Red
    Write-Host "Install Google Chrome, or edit tools/render-images.ps1 to point at your chrome.exe, then re-run this script." -ForegroundColor Red
    exit 1
}

Write-Host "Using Chrome: $chrome"

$ogHtml = Join-Path $root "src/og/og-card.html"
$iconHtml = Join-Path $root "src/og/icon-card.html"

$ogOut = Join-Path $root "src/assets/img/og-image.png"
$icon512Out = Join-Path $root "src/static/icon-512.png"
$appleOut = Join-Path $root "src/static/apple-touch-icon.png"
$favicon32Out = Join-Path $root "src/static/favicon-32.png"

New-Item -ItemType Directory -Force -Path (Split-Path $ogOut) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $icon512Out) | Out-Null

function Invoke-Screenshot {
    param(
        [string]$HtmlPath,
        [string]$OutPath,
        [int]$Width,
        [int]$Height
    )
    $uri = "file:///" + ($HtmlPath -replace '\\', '/')
    Write-Host "Rendering $OutPath ($Width x $Height) ..."
    if (Test-Path $OutPath) { Remove-Item $OutPath -Force }
    & $chrome --headless=new --disable-gpu --hide-scrollbars `
        --screenshot="$OutPath" `
        --window-size=$Width,$Height `
        $uri
    # Headless Chrome's launcher process can return before the screenshot
    # file is fully flushed to disk, so poll briefly instead of failing fast.
    $deadline = (Get-Date).AddSeconds(15)
    while (-not (Test-Path $OutPath) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Path $OutPath)) {
        throw "Chrome did not produce $OutPath"
    }
}

Invoke-Screenshot -HtmlPath $ogHtml -OutPath $ogOut -Width 1200 -Height 630
Invoke-Screenshot -HtmlPath $iconHtml -OutPath $icon512Out -Width 512 -Height 512
Invoke-Screenshot -HtmlPath $iconHtml -OutPath $appleOut -Width 180 -Height 180
Invoke-Screenshot -HtmlPath $iconHtml -OutPath $favicon32Out -Width 32 -Height 32

Write-Host "Building favicon.ico from favicon-32.png ..."
$python = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command "py" -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Host "ERROR: Python not found on PATH; cannot build favicon.ico. Run tools/make_favicon.py manually once Python is available." -ForegroundColor Red
    exit 1
}
& $python.Source (Join-Path $root "tools/make_favicon.py")

Write-Host "Done. Rendered images:"
Get-Item $ogOut, $icon512Out, $appleOut, $favicon32Out, (Join-Path $root "src/static/favicon.ico") | Format-Table Name, Length, FullName
