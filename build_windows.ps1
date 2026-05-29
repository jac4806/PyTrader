$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $AppDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

Set-Location $AppDir

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python no esta disponible en PATH. Instala Python 3.12 o superior y vuelve a ejecutar este script."
}

if (-not (Test-Path $PythonExe)) {
    python -m venv $VenvDir
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $AppDir "requirements.txt")
& $PythonExe -m pip install -r (Join-Path $AppDir "requirements-build.txt")
& $PythonExe -m PyInstaller --clean --noconfirm (Join-Path $AppDir "pytrader.spec")

$ExePath = Join-Path $AppDir "dist\PyTrader.exe"
if (-not (Test-Path $ExePath)) {
    throw "No se encontro el ejecutable esperado: $ExePath"
}

Write-Host "Ejecutable Windows creado en:"
Write-Host $ExePath
