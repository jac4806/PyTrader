#!/usr/bin/env bash
set -euo pipefail

echo "Instalador automático para PyTrader (Electron + Node.js)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

NO_SUDO=0
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --no-sudo) NO_SUDO=1; shift;;
    *) shift;;
  esac
done
command_exists() { command -v "$1" >/dev/null 2>&1; }

if command_exists node && command_exists npm; then
  echo "Node.js y npm ya están instalados: $(node -v) $(npm -v)"
else
  echo "Node.js/npm no detectados. Intentando instalar..."

  if [[ "$NO_SUDO" -eq 1 ]]; then
    echo "--no-sudo especificado: instalando nvm y Node.js en el usuario actual."
    if command_exists curl; then
      curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
    elif command_exists wget; then
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
    else
      echo "curl o wget no encontrado: instala Node.js manualmente y vuelve a ejecutar este script." >&2
      exit 1
    fi
    export NVM_DIR="${XDG_CONFIG_HOME:-$HOME/.nvm}"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    echo "Instalando Node.js LTS con nvm..."
    nvm install --lts
    nvm use --lts
  else
  if command_exists apt-get; then
    echo "Detectado apt-get (Debian/Ubuntu). Instalando Node.js 18.x..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs build-essential

  elif command_exists dnf; then
    echo "Detectado dnf (Fedora/RHEL). Instalando Node.js 18.x..."
    curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo -E bash -
    sudo dnf install -y nodejs

  elif command_exists pacman; then
    echo "Detectado pacman (Arch). Instalando nodejs + npm..."
    sudo pacman -S --noconfirm nodejs npm

  else
    echo "No se detectó gestor de paquetes compatible; se instalará nvm (usuario actual)."
    if command_exists curl; then
      curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
    elif command_exists wget; then
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
    else
      echo "curl o wget no encontrado: instala Node.js manualmente y vuelve a ejecutar este script." >&2
      exit 1
    fi

    export NVM_DIR="${XDG_CONFIG_HOME:-$HOME/.nvm}"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    echo "Instalando Node.js LTS con nvm..."
    nvm install --lts
    nvm use --lts
  fi
fi

echo "Instalando dependencias npm del proyecto..."
if ! command_exists npm; then
  echo "npm no está disponible después de la instalación. Revisa la instalación de Node.js y repite." >&2
  exit 1
fi

npm install

echo "Instalación completada. Para iniciar la app ejecuta:" 
echo "  npm run start"
echo "Si instalaste nvm, cierra y abre tu terminal o ejecuta: source ~/.nvm/nvm.sh"
