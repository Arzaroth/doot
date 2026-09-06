#!/usr/bin/env bash
# Desinstalle doot (Linux / macOS). Ajoute --purge pour effacer aussi les
# donnees (journal, jingle genere, sons perso).
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN_DIR="$HOME/.local/bin"
PURGE=0

[ "${1:-}" = "--purge" ] && PURGE=1

say() { printf '  %s\n' "$*"; }
printf '\n\033[1mdoot - desinstallation\033[0m\n'

# arret du daemon eventuel
if [ -x "$BIN_DIR/doot" ]; then
    "$BIN_DIR/doot" --stop >/dev/null 2>&1 || true
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user disable --now doot.service >/dev/null 2>&1 || true
    rm -f "$CONFIG_HOME/systemd/user/doot.service"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    say "systemd     : unite retiree"
fi

PLIST="$HOME/Library/LaunchAgents/com.doot.skeleton.plist"
if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" >/dev/null 2>&1 || true
    rm -f "$PLIST"
    say "LaunchAgent : retire"
fi

rm -f "$CONFIG_HOME/autostart/doot.desktop"
rm -f "$BIN_DIR/doot"
rm -rf "$DATA_HOME/doot/app"
say "commande    : retiree"

if [ "$PURGE" -eq 1 ]; then
    rm -rf "$DATA_HOME/doot"
    say "donnees     : effacees"
else
    say "donnees     : conservees dans $DATA_HOME/doot (--purge pour les effacer)"
fi

printf '\n  Plus de doot. Le squelette range sa trompette.\n\n'
