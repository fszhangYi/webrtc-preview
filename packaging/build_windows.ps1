#Requires -Version 5.1
<#
.SYNOPSIS
  Windows→Windows package for webrtc-preview (official CPython, no Miniconda).
  Prefer single timestamped exe; fallback flat onedir (no _internal) + timestamped zip.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Test-IsCondaPrefix([string]$Prefix) {
  $t = $Prefix.ToLower().Replace("/", "\")
  return ($t -match '\\miniconda') -or ($t -match '\\anaconda') -or ($t -match '\\conda\\')
}

function Stop-AppSafe {
  Get-Process | Where-Object {
    $_.ProcessName -eq "WebRTCPreview" -or $_.ProcessName -like "WebRTCPreview-*"
  } | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 1
}

function Invoke-PyInstaller([string]$Mode, [string]$Stamp) {
  $env:WEBRTC_PREVIEW_PACK_MODE = $Mode
  $env:WEBRTC_PREVIEW_PACK_STAMP = $Stamp
  Write-Host "[build] pyinstaller mode=$Mode stamp=$Stamp"
  & $script:VenvPy -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $script:Out `
    --workpath $script:Work `
    (Join-Path $Root "packaging\webrtc-preview.spec")
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($Mode)" }
}

function Test-Deliverable([string]$ExePath) {
  if (-not (Test-Path $ExePath)) { return $false }
  Write-Host "[build] smoke: $ExePath (cwd=C:\Windows, clean PATH)"
  $oldPath = $env:PATH
  $env:PATH = "C:\Windows\System32;C:\Windows"
  @("PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH") | ForEach-Object {
    Remove-Item "Env:$_" -ErrorAction SilentlyContinue
  }
  Get-ChildItem Env:CONDA* -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item "Env:$($_.Name)" -ErrorAction SilentlyContinue
  }
  $p = $null
  try {
    $p = Start-Process -FilePath $ExePath -WorkingDirectory "C:\Windows" -PassThru
    $healthy = $false
    $title = ""
    for ($i = 0; $i -lt 60; $i++) {
      Start-Sleep -Seconds 1
      if ($p.HasExited) {
        Write-Warning "[build] smoke exited early code=$($p.ExitCode)"
        return $false
      }
      if (-not $healthy) {
        try {
          $r = Invoke-WebRequest -Uri "http://127.0.0.1:7050/api/health" -UseBasicParsing -TimeoutSec 1
          if ($r.StatusCode -eq 200) { $healthy = $true }
        } catch {}
      }
      $procs = @($p) + @(Get-Process | Where-Object {
          $_.Id -ne $p.Id -and ($_.ProcessName -eq $p.ProcessName -or $_.ProcessName -eq "WebRTCPreview")
        })
      foreach ($proc in $procs) {
        try { $proc.Refresh() } catch { continue }
        if ($proc.MainWindowTitle) { $title = $proc.MainWindowTitle; break }
      }
      if ($healthy -and $title) { break }
      if ($healthy -and $i -ge 35) { break }
    }
    Write-Host "[build] smoke title='$title' health=$healthy"
    return [bool]$healthy
  } finally {
    if ($p -and -not $p.HasExited) {
      Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
      Start-Sleep -Seconds 1
    }
    $env:PATH = $oldPath
  }
}

function Test-OnedirChecklist([string]$Dir) {
  $must = @(
    "QtWebEngineProcess.exe", "qwindows.dll", "d3dcompiler_47.dll",
    "icudtl.dat", "qtwebengine_resources.pak", "index.html",
    "VCRUNTIME140.dll", "VCRUNTIME140_1.dll"
  )
  $names = @{}
  Get-ChildItem -Path $Dir -Recurse -File | ForEach-Object { $names[$_.Name.ToLower()] = $true }
  $missing = @($must | Where-Object { -not $names.ContainsKey($_.ToLower()) })
  if ($missing.Count) { Write-Warning ("Missing: " + ($missing -join ", ")); return $false }
  if (Test-Path (Join-Path $Dir "_internal")) {
    Write-Warning "_internal present — contents_directory not applied"
    return $false
  }
  $forbid = Get-ChildItem -Path $Dir -Recurse -File | Where-Object {
    $_.Name -like "api-ms-win-*" -or $_.Name -eq "ucrtbase.dll" -or $_.Name -eq "libtommath.dll"
  }
  if ($forbid) {
    Write-Warning ("Forbidden DLLs: " + (($forbid | ForEach-Object Name) -join ", "))
    return $false
  }
  return $true
}

function New-AppZip([string]$Dir, [string]$Stamp) {
  $zipPath = Join-Path $script:Out ("WebRTCPreview-" + $Stamp + ".zip")
  if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  [System.IO.Compression.ZipFile]::CreateFromDirectory($Dir, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)
  # Convenience launchers inside dist (also copied into zip folder before zip)
  return $zipPath
}

$Build = Join-Path $Root "build"
$Cpython = Join-Path $Build "cpython"
$PackVenv = Join-Path $Build "packvenv"
$PyExe = Join-Path $Cpython "python.exe"
$script:VenvPy = Join-Path $PackVenv "Scripts\python.exe"
$script:Out = Join-Path $Root "dist"
$script:Work = Join-Path $Build "pyi"
$ver = "3.12.8"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

New-Item -ItemType Directory -Force -Path $Build, $script:Out, $script:Work | Out-Null

$Ico = Join-Path $Root "packaging\webrtc-preview.ico"
if (-not (Test-Path $Ico)) {
  Write-Host "[build] generating icon"
  # Prefer packvenv later; use workspace or system python for pillow once
  $pyForIcon = $null
  foreach ($cand in @(
      (Join-Path $Root "..\.venv\Scripts\python.exe"),
      $script:VenvPy,
      $PyExe
    )) {
    if ($cand -and (Test-Path $cand)) { $pyForIcon = $cand; break }
  }
  if (-not $pyForIcon) { $pyForIcon = "python" }
  & $pyForIcon -m pip install pillow -q --no-warn-script-location 2>$null
  & $pyForIcon (Join-Path $Root "packaging\make_icon.py")
  if (-not (Test-Path $Ico)) { throw "missing packaging/webrtc-preview.ico" }
}

# --- 1) Official CPython embeddable ---
if (-not (Test-Path $PyExe)) {
  $zip = Join-Path $Build "python-$ver-embed-amd64.zip"
  $url = "https://www.python.org/ftp/python/$ver/python-$ver-embed-amd64.zip"
  Write-Host "[build] downloading embeddable $url"
  Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
  if (Test-Path $Cpython) { Remove-Item -Recurse -Force $Cpython }
  New-Item -ItemType Directory -Force -Path $Cpython | Out-Null
  Expand-Archive -Path $zip -DestinationPath $Cpython -Force
  $pth = Get-ChildItem $Cpython -Filter "python*._pth" | Select-Object -First 1
  if ($pth) {
    $text = Get-Content $pth.FullName -Raw
    if ($text -notmatch "(?m)^import site\s*$") {
      $text = $text -replace "(?m)^#import site\s*$", "import site"
      if ($text -notmatch "(?m)^import site\s*$") { $text = $text.TrimEnd() + "`r`nimport site`r`n" }
    }
    if ($text -notmatch "Lib\\site-packages") {
      $text = $text.TrimEnd() + "`r`nLib\\site-packages`r`n"
    }
    Set-Content -Path $pth.FullName -Value $text -Encoding ASCII
  }
  $getPip = Join-Path $Build "get-pip.py"
  Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
  & $PyExe $getPip --no-warn-script-location
  if ($LASTEXITCODE -ne 0) { throw "get-pip failed" }
}

$basePrefix = & $PyExe -c "import sys; print(sys.base_prefix)"
if (Test-IsCondaPrefix $basePrefix) {
  throw "Refuse conda/miniconda prefix: $basePrefix"
}

if (-not (Test-Path $script:VenvPy)) {
  Write-Host "[build] creating packvenv"
  & $PyExe -m pip install -U pip setuptools wheel virtualenv --no-warn-script-location
  & $PyExe -m virtualenv $PackVenv
  if (-not (Test-Path $script:VenvPy)) { $script:VenvPy = $PyExe }
}

Write-Host "[build] pip install deps ($script:VenvPy)"
& $script:VenvPy -m pip install -U pip setuptools wheel pillow --no-warn-script-location
& $script:VenvPy -m pip install -e "$Root" --no-warn-script-location
& $script:VenvPy -m pip install "pyinstaller>=6.3" "PyQt5>=5.15" "PyQtWebEngine>=5.15" --no-warn-script-location

if (-not (Test-Path $Ico)) {
  & $script:VenvPy (Join-Path $Root "packaging\make_icon.py")
}

Stop-AppSafe

# --- Prefer onefile ---
Invoke-PyInstaller -Mode "onefile" -Stamp $Stamp
$oneExe = Join-Path $script:Out ("WebRTCPreview-" + $Stamp + ".exe")
$oneOk = Test-Deliverable -ExePath $oneExe
if ($oneOk) {
  # Sidecar bats next to onefile for convenience (optional)
  # Packaged default: headless + system browser (规则 §1). --ui = PyQt shell.
  $startWeb = @"
@echo off
start `"`" `"%~dp0WebRTCPreview-$Stamp.exe`"
"@
  $startDesk = @"
@echo off
start `"`" `"%~dp0WebRTCPreview-$Stamp.exe`" --ui
"@
  Set-Content -Path (Join-Path $script:Out "start_web.bat") -Value $startWeb -Encoding ASCII
  Set-Content -Path (Join-Path $script:Out "start_desktop.bat") -Value $startDesk -Encoding ASCII
  Write-Host "[build] DONE (onefile) -> $oneExe"
  Write-Host "Deliver this single exe. Target: 64-bit Windows 10+."
  exit 0
}

Write-Warning "[build] onefile smoke failed — falling back to flat onedir + zip"
Stop-AppSafe

Invoke-PyInstaller -Mode "onedir" -Stamp $Stamp
$Dir = Join-Path $script:Out "WebRTCPreview"
if (-not (Test-Path (Join-Path $Dir "WebRTCPreview.exe"))) {
  throw "missing dist/WebRTCPreview/WebRTCPreview.exe after onedir build"
}
if (-not (Test-OnedirChecklist -Dir $Dir)) {
  throw "onedir checklist failed"
}

# Launch helpers inside the folder (then into zip)
# start_web = headless + browser; start_desktop = PyQt --ui
@"
@echo off
cd /d `"%~dp0`"
start `"`" `"%~dp0WebRTCPreview.exe`" --ui
"@ | Set-Content -Path (Join-Path $Dir "start_desktop.bat") -Encoding ASCII
@"
@echo off
cd /d `"%~dp0`"
start `"`" `"%~dp0WebRTCPreview.exe`"
"@ | Set-Content -Path (Join-Path $Dir "start_web.bat") -Encoding ASCII

$zipOut = New-AppZip -Dir $Dir -Stamp $Stamp
$zipOk = Test-Deliverable -ExePath (Join-Path $Dir "WebRTCPreview.exe")
if (-not $zipOk) {
  Write-Warning "[build] onedir smoke did not fully pass; zip still written"
}
Write-Host "[build] DONE (zip) -> $zipOut"
Write-Host "Deliver the zip only (no loose _internal). Extract then run WebRTCPreview.exe."
