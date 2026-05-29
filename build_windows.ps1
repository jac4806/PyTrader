param(
    [switch]$Install
)

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
& (Join-Path $AppDir "package_windows.ps1") -ExePath $ExePath
if ($Install) {
    $WScript = New-Object -ComObject WScript.Shell
    $DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "PyTrader.lnk"
    $StartMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "PyTrader"
    $StartMenuShortcut = Join-Path $StartMenuDir "PyTrader.lnk"

    New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null

    foreach ($ShortcutPath in @($DesktopShortcut, $StartMenuShortcut)) {
        $Shortcut = $WScript.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = $ExePath
        $Shortcut.WorkingDirectory = $AppDir
        $Shortcut.Description = "Smart Money stock screener"
        $Shortcut.Save()
    }
}

Write-Host $ExePath
if ($Install) {
    Write-Host "Instalado tambien con accesos directos en Escritorio y menu Inicio."
}
