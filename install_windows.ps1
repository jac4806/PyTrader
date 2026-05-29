$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $AppDir ".venv"
$Launcher = Join-Path $AppDir "pytrader.bat"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python no esta disponible en PATH. Instala Python y vuelve a ejecutar este instalador."
}

if (-not (Test-Path $PythonExe)) {
    python -m venv $VenvDir
}

& $PythonExe -m pip install --upgrade pip
& $PipExe install -r (Join-Path $AppDir "requirements.txt")

@"
@echo off
cd /d "$AppDir"
"$PythonExe" "$AppDir\F_Trader_4.py"
"@ | Set-Content -LiteralPath $Launcher -Encoding ASCII

$WScript = New-Object -ComObject WScript.Shell
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "PyTrader.lnk"
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "PyTrader"
$StartMenuShortcut = Join-Path $StartMenuDir "PyTrader.lnk"

New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null

foreach ($ShortcutPath in @($DesktopShortcut, $StartMenuShortcut)) {
    $Shortcut = $WScript.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $Launcher
    $Shortcut.WorkingDirectory = $AppDir
    $Shortcut.Description = "Smart Money stock screener"
    $Shortcut.Save()
}

Write-Host "PyTrader instalado."
Write-Host "Puedes abrirlo desde el acceso directo del Escritorio, el menu Inicio o ejecutando:"
Write-Host $Launcher
