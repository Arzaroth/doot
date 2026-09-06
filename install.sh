#!/usr/bin/env bash
# Installe doot pour l'utilisateur courant (Linux, y compris Arch, et macOS).
#
#   ./install.sh                 # installe + demarrage automatique a la session
#   ./install.sh --no-autostart  # installe seulement la commande `doot`
#   ./install.sh --min 300 --max 1800
#
# Aucun droit root, aucune dependance Python : tout est dans la stdlib.
set -euo pipefail

APP_NAME="doot"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$DATA_HOME/$APP_NAME/app"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Dossier de donnees de doot, qui n'est pas celui du code : sur macOS c'est
# Application Support quand le code va dans ~/.local/share.
if [ "$(uname -s)" = "Darwin" ]; then
    RECORD_DIR="$HOME/Library/Application Support/$APP_NAME"
else
    RECORD_DIR="$DATA_HOME/$APP_NAME"
fi

AUTOSTART=1
MIN_SECONDS=600
MAX_SECONDS=3600

while [ $# -gt 0 ]; do
    case "$1" in
        --no-autostart) AUTOSTART=0; shift ;;
        --min) MIN_SECONDS="$2"; shift 2 ;;
        --max) MAX_SECONDS="$2"; shift 2 ;;
        -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
        *) echo "option inconnue : $1" >&2; exit 2 ;;
    esac
done

say()  { printf '  %s\n' "$*"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$*"; }

head_ "doot - installation"

# ------------------------------------------------------------ python ---------
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)'; then
            PYTHON="$(command -v "$candidate")"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    say "Python 3.8+ est introuvable. Installe-le puis relance :"
    say "  Arch/Manjaro  : sudo pacman -S python tk"
    say "  Debian/Ubuntu : sudo apt install python3 python3-tk"
    say "  Fedora        : sudo dnf install python3 python3-tkinter"
    say "  macOS         : brew install python-tk"
    exit 1
fi
say "python      : $PYTHON ($("$PYTHON" -c 'import platform; print(platform.python_version())'))"

# ------------------------------------------------------------ tkinter --------
if ! "$PYTHON" -c 'import tkinter' >/dev/null 2>&1; then
    say "tkinter     : MANQUANT (l'overlay ne s'affichera pas)"
    if   command -v pacman  >/dev/null 2>&1; then say "  -> sudo pacman -S tk"
    elif command -v apt     >/dev/null 2>&1; then say "  -> sudo apt install python3-tk"
    elif command -v dnf     >/dev/null 2>&1; then say "  -> sudo dnf install python3-tkinter"
    elif command -v zypper  >/dev/null 2>&1; then say "  -> sudo zypper install python3-tk"
    elif command -v brew    >/dev/null 2>&1; then say "  -> brew install python-tk"
    fi
    say "  (l'installation continue, tu pourras l'ajouter apres)"
else
    say "tkinter     : OK"
fi

# ------------------------------------------------------------- audio ---------
if [ "$(uname -s)" = "Darwin" ]; then
    say "audio       : afplay (integre a macOS)"
else
    PLAYER=""
    for p in pw-play paplay aplay ffplay play mpv cvlc; do
        if command -v "$p" >/dev/null 2>&1; then PLAYER="$p"; break; fi
    done
    if [ -n "$PLAYER" ]; then
        say "audio       : $PLAYER"
    else
        say "audio       : aucun lecteur trouve (doot restera muet)"
        command -v pacman >/dev/null 2>&1 && say "  -> sudo pacman -S alsa-utils    (ou pipewire-audio / libpulse)"
    fi
fi

# ------------------------------------------------------------ fichiers -------
head_ "Copie des fichiers"

# Un daemon deja lance continuerait avec l'ancien code : on l'arrete, et on le
# relance en fin d'installation s'il tournait.
DAEMON_TOURNAIT=0
if [ -f "$RECORD_DIR/doot.pid" ]; then
    DAEMON_PID="$(cat "$RECORD_DIR/doot.pid" 2>/dev/null || true)"
    if [ -n "$DAEMON_PID" ] && kill -0 "$DAEMON_PID" 2>/dev/null; then
        kill "$DAEMON_PID" 2>/dev/null || true
        rm -f "$RECORD_DIR/doot.pid"
        DAEMON_TOURNAIT=1
        say "daemon      : arrete (pid $DAEMON_PID) le temps de la copie"
    fi
fi

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR" "$BIN_DIR"
cp -R "$SRC_DIR/doot" "$APP_DIR/doot"
say "code        : $APP_DIR/doot"

cat > "$BIN_DIR/doot" <<EOF
#!/usr/bin/env bash
# Lanceur genere par install.sh
export PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$PYTHON" -m doot "\$@"
EOF
chmod +x "$BIN_DIR/doot"
say "commande    : $BIN_DIR/doot"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) say "ATTENTION   : $BIN_DIR n'est pas dans ton PATH"
       say "  -> ajoute  export PATH=\"\$HOME/.local/bin:\$PATH\"  a ton ~/.bashrc / ~/.zshrc" ;;
esac

# Fiche d'installation, relue par `doot --update`.
COMMIT=""
if [ -d "$SRC_DIR/.git" ] && command -v git >/dev/null 2>&1; then
    COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || true)"
fi
mkdir -p "$RECORD_DIR"
cat > "$RECORD_DIR/install.json" <<EOF
{
  "source": "$SRC_DIR",
  "commit": "$COMMIT",
  "min": $MIN_SECONDS,
  "max": $MAX_SECONDS,
  "autostart": $([ "$AUTOSTART" -eq 1 ] && echo true || echo false),
  "app_dir": "$APP_DIR",
  "bin_dir": "$BIN_DIR",
  "python": "$PYTHON",
  "platform": "$(uname -s)",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
say "fiche       : $RECORD_DIR/install.json"

# --------------------------------------------------------- demarrage ---------
if [ "$AUTOSTART" -eq 1 ]; then
    head_ "Demarrage automatique"
    if [ "$(uname -s)" = "Darwin" ]; then
        PLIST="$HOME/Library/LaunchAgents/com.doot.skeleton.plist"
        mkdir -p "$(dirname "$PLIST")"
        cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.doot.skeleton</string>
    <key>ProgramArguments</key>
    <array>
        <string>$BIN_DIR/doot</string>
        <string>--min</string><string>$MIN_SECONDS</string>
        <string>--max</string><string>$MAX_SECONDS</string>
        <string>--quiet</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ProcessType</key><string>Interactive</string>
</dict>
</plist>
EOF
        launchctl unload "$PLIST" >/dev/null 2>&1 || true
        launchctl load "$PLIST"
        say "LaunchAgent : $PLIST (charge)"
    elif command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
        UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
        mkdir -p "$UNIT_DIR"
        cat > "$UNIT_DIR/doot.service" <<EOF
[Unit]
Description=doot - squelette trompettiste saisonnier
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$BIN_DIR/doot --min $MIN_SECONDS --max $MAX_SECONDS --quiet
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable doot.service >/dev/null 2>&1 || true
        # restart et pas `enable --now` : sur une reinstallation l'unite tourne
        # deja, et --now ne relancerait pas le code fraichement copie.
        systemctl --user restart doot.service
        DAEMON_TOURNAIT=0
        say "systemd     : doot.service actif (systemctl --user status doot)"
    else
        DESKTOP_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
        mkdir -p "$DESKTOP_DIR"
        cat > "$DESKTOP_DIR/doot.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=doot
Comment=Squelette trompettiste saisonnier
Exec=$BIN_DIR/doot --min $MIN_SECONDS --max $MAX_SECONDS --quiet
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
        say "autostart   : $DESKTOP_DIR/doot.desktop"
    fi
else
    say "demarrage automatique ignore (--no-autostart)"
fi

# Hors systemd, on relance nous-memes le daemon qui tournait avant la copie.
if [ "$DAEMON_TOURNAIT" -eq 1 ]; then
    "$BIN_DIR/doot" --min "$MIN_SECONDS" --max "$MAX_SECONDS" --quiet \
        >/dev/null 2>&1 &
    say "daemon      : redemarre avec le nouveau code"
fi

head_ "Termine"
say "Teste tout de suite : doot --once --ignore-season"
say "Etat                : doot --status"
say "Desinstaller        : ./uninstall.sh"
printf '\n'
"$BIN_DIR/doot" --art || true
