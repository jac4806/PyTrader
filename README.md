# PyTrader

Aplicacion de escritorio en Python/PyQt6 para analizar tickers con yfinance.

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
