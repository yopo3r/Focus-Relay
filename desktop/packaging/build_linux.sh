#!/usr/bin/env bash
# Genera FocusRelay-linux.tar.gz (programa independiente + instalador de menú). Requiere python3-tk instalado al compilar.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install --upgrade pyinstaller -r requirements.txt
pyinstaller --noconfirm focus_relay.spec
cp assets/icon-256.png dist/FocusRelay/focus-relay.png
cp packaging/install_linux_bundle.sh dist/FocusRelay/instalar.sh
chmod +x dist/FocusRelay/instalar.sh
tar -C dist -czf dist/FocusRelay-linux.tar.gz FocusRelay
echo "Listo: dist/FocusRelay-linux.tar.gz"
