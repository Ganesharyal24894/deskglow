#!/usr/bin/env bash
# Remove everything install.sh set up (app, command, service, icon).
# Leaves the project folder and your saved settings alone.
set -uo pipefail

BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor"
UNIT_DIR="$HOME/.config/systemd/user"

echo "Removing the Light LED controller…"

# service
systemctl --user disable --now sc295d.service 2>/dev/null || true
rm -f "$UNIT_DIR/sc295d.service"
systemctl --user daemon-reload 2>/dev/null || true

# commands
rm -f "$BIN/sc295" "$BIN/sc295-gui"

# launcher + icons
rm -f "$APPS/light.desktop" "$APPS/sc295.desktop"
rm -f "$ICONS/scalable/apps/sc295-light.svg"
for s in 48 64 128 256; do rm -f "$ICONS/${s}x${s}/apps/sc295-light.png"; done
update-desktop-database "$APPS" 2>/dev/null || true

echo "Done."
echo "Your settings are still in ~/.config/sc295 (delete it to fully reset)."
echo "The project folder and its .venv were left in place; delete them if you like."
