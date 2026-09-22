#!/usr/bin/env bash
# Instala o WatchAI no desktop: comando `watchai` no PATH, lançador no menu e
# (opcional) atalho na área de trabalho.
#
#   ./scripts/install-linux.sh                 # comando + menu
#   ./scripts/install-linux.sh --desktop       # ...e atalho na área de trabalho
#   ./scripts/install-linux.sh --uninstall     # desfaz
#
# Não mexe no sistema: tudo vai para ~/.local, que é do usuário.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$HOME/.local/bin/watchai"
LANCADOR="$HOME/.local/share/applications/watchai.desktop"
ICONE="$HOME/.local/share/icons/hicolor/scalable/apps/watchai.svg"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$BIN" "$LANCADOR" "$ICONE" "$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")/watchai.desktop"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo "WatchAI removido (o repositório continua em $RAIZ)."
    exit 0
fi

# 1. ambiente
if [[ ! -x "$RAIZ/.venv/bin/python" ]]; then
    echo "→ criando o ambiente virtual"
    python3 -m venv "$RAIZ/.venv"
fi
echo "→ instalando as dependências"
"$RAIZ/.venv/bin/pip" install --quiet --upgrade pip
"$RAIZ/.venv/bin/pip" install --quiet -e "$RAIZ"

# 2. comando no PATH
mkdir -p "$(dirname "$BIN")"
cat > "$BIN" <<WRAP
#!/bin/sh
# WatchAI — monitor de sessões de IA no terminal.
# Usa o venv do projeto; se ele sumir, cai no python do sistema.
DIR="$RAIZ"
if [ -x "\$DIR/.venv/bin/watchai" ]; then
    exec "\$DIR/.venv/bin/watchai" "\$@"
fi
exec python3 "\$DIR/main.py" "\$@"
WRAP
chmod +x "$BIN"

# 3. ícone e lançador
mkdir -p "$(dirname "$ICONE")" "$(dirname "$LANCADOR")"
cp "$RAIZ/assets/watchai.svg" "$ICONE"
cat > "$LANCADOR" <<DESK
[Desktop Entry]
Type=Application
Version=1.0
Name=WatchAI
GenericName=AI Session Monitor
Comment=Suas sessões de IA (Claude Code, Codex, Gemini…) em uma tela só
Exec=$BIN
Icon=$ICONE
Terminal=true
Categories=System;Monitor;ConsoleOnly;
Keywords=ai;claude;codex;gemini;monitor;terminal;tui;sessions;
StartupNotify=false
DESK
chmod +x "$LANCADOR"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# 4. área de trabalho (opcional)
if [[ "${1:-}" == "--desktop" ]]; then
    AREA="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
    if [[ -d "$AREA" ]]; then
        cp "$LANCADOR" "$AREA/watchai.desktop"
        chmod +x "$AREA/watchai.desktop"
        gio set "$AREA/watchai.desktop" metadata::trusted true 2>/dev/null || true
        echo "→ atalho em $AREA"
    fi
fi

echo
echo "pronto:"
echo "  comando   watchai            (se não achar, abra um terminal novo)"
echo "  menu      WatchAI"
"$BIN" --version
