# PyTrader

Aplicacion de escritorio en Python/PyQt6 para analizar tickers con yfinance.

## Correo de resultados

Al finalizar el analisis, la aplicacion envia a `titogilito64@gmail.com` los
resultados con `Score` superior a `80` si estan configuradas estas variables:

```bash
PYTRADER_SMTP_HOST=smtp.gmail.com
PYTRADER_SMTP_PORT=587
PYTRADER_SMTP_USER=tu_correo@gmail.com
PYTRADER_SMTP_PASSWORD=tu_password_de_aplicacion
PYTRADER_SMTP_FROM=tu_correo@gmail.com
```

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
