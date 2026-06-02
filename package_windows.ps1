param(
    [string]$ExePath = ""
)

$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DistDir = Join-Path $AppDir "dist"
$PackageName = "PyTrader-windows11-x64"
$PackageDir = Join-Path $DistDir $PackageName
$ZipPath = Join-Path $DistDir "$PackageName.zip"

if (-not $ExePath) {
    $ExePath = Join-Path $DistDir "PyTrader.exe"
}

if (-not (Test-Path $ExePath)) {
    throw "No se encontro $ExePath. Ejecuta este empaquetador en Windows despues de build_windows.ps1."
}

Remove-Item -Recurse -Force $PackageDir -ErrorAction SilentlyContinue
Remove-Item -Force $ZipPath -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

Copy-Item -LiteralPath $ExePath -Destination (Join-Path $PackageDir "PyTrader.exe") -Force

@'
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA "PyTrader"
$ExePath = Join-Path $InstallDir "PyTrader.exe"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -LiteralPath (Join-Path $ScriptDir "PyTrader.exe") -Destination $ExePath -Force

$WScript = New-Object -ComObject WScript.Shell
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "PyTrader.lnk"
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "PyTrader"
$StartMenuShortcut = Join-Path $StartMenuDir "PyTrader.lnk"

New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null

foreach ($ShortcutPath in @($DesktopShortcut, $StartMenuShortcut)) {
    $Shortcut = $WScript.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $ExePath
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "Smart Money stock screener"
    $Shortcut.Save()
}

Write-Host "PyTrader instalado en: $InstallDir"
Write-Host "Accesos directos creados en Escritorio y menu Inicio."
'@ | Set-Content -LiteralPath (Join-Path $PackageDir "install_windows11.ps1") -Encoding ASCII

@'
PyTrader para Windows 11 x64

Instalacion:
1. Descomprime este paquete.
2. Click derecho sobre install_windows11.ps1.
3. Elige "Run with PowerShell".

El instalador copia PyTrader.exe a %LOCALAPPDATA%\PyTrader y crea accesos directos
en el Escritorio y en el menu Inicio.
'@ | Set-Content -LiteralPath (Join-Path $PackageDir "README.txt") -Encoding ASCII

Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -Force
Write-Host "Instalable Windows 11 creado en:"
Write-Host $ZipPath
