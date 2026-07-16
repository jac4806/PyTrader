#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
LAUNCHER="$HOME/.local/bin/pytrader"
DESKTOP_FILE="$HOME/.local/share/applications/pytrader.desktop"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.local/share/applications"

cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
cd "$APP_DIR"
exec "$VENV_DIR/bin/python" "$APP_DIR/F_Trader_4.py"
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

echo "PyTrader instalado."
echo "Puedes abrirlo desde el menu de aplicaciones o ejecutar: pytrader"
