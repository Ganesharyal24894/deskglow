#!/usr/bin/env bash
# Remove everything install.sh set up (command and service), including any
# leftovers from the pre-rename "sc295" install.
# Leaves the project folder and your saved settings alone.
set -uo pipefail

BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor"
UNIT_DIR="$HOME/.config/systemd/user"

echo "Removing Deskglow…"

if [ "$(uname -s)" = "Darwin" ]; then
  # the LaunchAgent (stop it, then forget it)
  PLIST="$HOME/Library/LaunchAgents/io.deskglow.daemon.plist"
  launchctl bootout "gui/$(id -u)/io.deskglow.daemon" 2>/dev/null || true
  rm -f "$PLIST"
else
  # services (current, and the pre-rename one)
  for unit in deskglowd.service sc295d.service; do
    systemctl --user disable --now "$unit" 2>/dev/null || true
    rm -f "$UNIT_DIR/$unit"
  done
  systemctl --user daemon-reload 2>/dev/null || true
  # the XDG autostart fallback used where systemd --user is unavailable
  rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/deskglowd.desktop"
fi

# commands
rm -f "$BIN/deskglow" "$BIN/sc295" "$BIN/sc295-gui"

# launchers + icons left by older versions
rm -f "$APPS/light.desktop" "$APPS/sc295.desktop"
rm -f "$ICONS/scalable/apps/sc295-light.svg"
for s in 48 64 128 256; do rm -f "$ICONS/${s}x${s}/apps/sc295-light.png"; done
update-desktop-database "$APPS" 2>/dev/null || true

echo "Done."
echo "Your settings are still in ~/.config/deskglow (macOS: ~/Library/Application"
echo "Support/deskglow); delete it to fully reset. ~/.config/sc295 may also exist"
echo "from before the rename."
echo "The project folder and its .venv were left in place; delete them if you like."
