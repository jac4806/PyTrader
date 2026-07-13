#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_DESKTOP="${1:-}"

cd "$APP_DIR"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
"$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements-build.txt"
"$VENV_DIR/bin/python" -m PyInstaller --clean --noconfirm "$APP_DIR/pytrader.spec"

chmod +x "$APP_DIR/dist/PyTrader"

if [[ "$INSTALL_DESKTOP" == "--install" ]]; then
    LAUNCHER="$HOME/.local/bin/pytrader"
    DESKTOP_FILE="$HOME/.local/share/applications/pytrader.desktop"

    mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"

    cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
cd "$APP_DIR"
exec "$APP_DIR/dist/PyTrader"
EOF
    chmod +x "$LAUNCHER"

    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=PyTrader
Comment=Smart Money stock screener
Exec=$LAUNCHER
Path=$APP_DIR
Icon=$APP_DIR/lupa-diagrama-negocios.png
Terminal=false
Categories=Office;Finance;
StartupNotify=true
EOF

    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
    fi
fi

echo "Ejecutable Linux creado en: $APP_DIR/dist/PyTrader"
if [[ "$INSTALL_DESKTOP" == "--install" ]]; then
    echo "Instalado tambien como comando: pytrader"
fi
