# PyTrader

Aplicacion de escritorio en Python/PyQt6 para analizar tickers con yfinance.

## Instalar en Windows

Desde PowerShell, en la carpeta del proyecto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1
```

El instalador crea:

- un entorno virtual en `.venv`
- el lanzador `pytrader.bat`
- accesos directos en el Escritorio y en el menu Inicio

## Correo de resultados

Al finalizar el analisis, la aplicacion envia a `titogilito64@gmail.com` los
resultados con `Score` superior a `80` si estan configuradas estas variables.
Puedes definirlas en el entorno del sistema o crear un archivo `.env` en la
carpeta del proyecto usando `.env.example` como plantilla:

```bash
PYTRADER_SMTP_HOST=smtp.gmail.com
PYTRADER_SMTP_PORT=587
PYTRADER_SMTP_USER=tu_correo@gmail.com
PYTRADER_SMTP_PASSWORD=tu_password_de_aplicacion
PYTRADER_SMTP_FROM=tu_correo@gmail.com
```

Para Gmail, `PYTRADER_SMTP_PASSWORD` debe ser una contrasena de aplicacion, no
la contrasena normal de la cuenta.

## Instalar en Linux

Desde la carpeta del proyecto:

```bash
chmod +x install_linux.sh
./install_linux.sh
```

El instalador crea:

- un entorno virtual en `.venv`
- el comando `pytrader` en `~/.local/bin`
- una entrada de escritorio en `~/.local/share/applications/pytrader.desktop`

Si `~/.local/bin` no esta en tu `PATH`, puedes abrir la aplicacion desde el menu
de Linux o ejecutar directamente:

```bash
~/.local/bin/pytrader
```

## Crear ejecutable para Linux

Desde Linux:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

El ejecutable queda en:

```bash
dist/PyTrader
```

Para crear el ejecutable e instalarlo en el menu de aplicaciones:

```bash
./build_linux.sh --install
```

## Crear ejecutable para Windows 11

El `.exe` debe generarse en Windows. Desde PowerShell, en la carpeta del
proyecto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1
```

Para crear el ejecutable e instalar accesos directos en el Escritorio y el menu Inicio:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1 -Install
```

El ejecutable queda en:

```powershell
dist\PyTrader.exe
```
