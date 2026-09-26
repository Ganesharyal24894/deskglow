#!/usr/bin/env bash
# One-command setup for Deskglow, the Bluetooth LED strip controller.
# Installs system + python dependencies, the `deskglow` CLI and the `deskglowd`
# background service, then helps you find your strip. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OS="$(uname -s)"
case "$OS" in
  Linux|Darwin) ;;
  *) echo "install.sh supports Linux and macOS. On Windows, follow the README's"
     echo "\"Windows\" install steps (PowerShell)."; exit 1 ;;
esac
PY="$ROOT/.venv/bin/python"
BIN="$HOME/.local/bin"
UNIT_DIR="$HOME/.config/systemd/user"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor"

echo "=================================================="
echo "  Deskglow — LED strip setup"
echo "=================================================="
echo "project: $ROOT"
echo

# 0) system dependencies ----------------------------------------------------
# Set DESKGLOW_NO_APT=1 to skip this step entirely and install the system
# packages yourself. Nothing else in this script needs sudo.
WANT="python3 python3-venv bluez"
# Wayland screen mode reads the portal's PipeWire stream through GStreamer
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
  WANT="$WANT gstreamer1.0-tools gstreamer1.0-pipewire"
fi
if [ "$OS" = "Darwin" ]; then
  echo "macOS: no system packages needed (Python 3.10+ from python.org or Homebrew)."
elif command -v apt-get >/dev/null 2>&1; then
  missing=""
  for pkg in $WANT; do
    dpkg -s "$pkg" >/dev/null 2>&1 || missing="$missing $pkg"
  done
  if [ -n "$missing" ]; then
    echo "The following system packages are missing:$missing"
    if [ -n "${DESKGLOW_NO_APT:-}" ]; then
      echo "DESKGLOW_NO_APT is set — skipping the system package step."
      echo "Install them yourself with:"
      echo "  sudo apt-get install -y$missing"
    else
      echo "This step will run, as root:"
      echo "  sudo apt-get update -qq"
      echo "  sudo apt-get install -y$missing"
      echo "(you may be asked for your password; re-run with DESKGLOW_NO_APT=1 to skip)"
      sudo apt-get update -qq || true
      sudo apt-get install -y $missing
    fi
  else
    echo "System packages already installed."
  fi
else
  echo "NOTE: non-Debian/Ubuntu system detected. Please make sure these are"
  echo "      installed: $WANT"
  echo "      (Fedora: gstreamer1-plugins-base-tools gstreamer1-plugin-pipewire;"
  echo "       Arch: gstreamer gst-plugin-pipewire — only needed on Wayland)"
fi
echo

# 1) retire the pre-rename install (sc295) ---------------------------------
# Deskglow used to be called sc295. Stop and remove its service and launchers
# so two daemons never fight over the strip. Settings in ~/.config/sc295 are
# copied to ~/.config/deskglow automatically on first run.
if [ "$OS" = "Linux" ] && { [ -f "$UNIT_DIR/sc295d.service" ] || systemctl --user cat sc295d.service >/dev/null 2>&1; }; then
  echo "Removing the old sc295d.service…"
  systemctl --user disable --now sc295d.service 2>/dev/null || true
  rm -f "$UNIT_DIR/sc295d.service"
  systemctl --user daemon-reload 2>/dev/null || true
fi
for old in "$BIN/sc295" "$BIN/sc295-gui"; do
  if [ -e "$old" ]; then rm -f "$old"; echo "removed old launcher $old"; fi
done
# the Tkinter "Light" app is gone; a new desktop app comes in a later release
rm -f "$APPS/light.desktop" "$APPS/sc295.desktop"
rm -f "$ICONS/scalable/apps/sc295-light.svg"
for s in 48 64 128 256; do rm -f "$ICONS/${s}x${s}/apps/sc295-light.png"; done

# 2) venv + python deps -----------------------------------------------------
if [ ! -x "$PY" ]; then
  echo "Creating Python environment…"
  python3 -m venv "$ROOT/.venv"
fi
echo "Installing Python packages…"
"$ROOT/.venv/bin/pip" install --quiet --upgrade pip
# install the project itself (editable, with every optional extra) so the venv
# gets exactly what pyproject.toml declares
"$ROOT/.venv/bin/pip" install --quiet -e "$ROOT[all]"
# Linux X11 global shortcut: pynput needs evdev, which compiles from source;
# best effort, everything else works without it.
if [ "$OS" = "Linux" ] && ! "$PY" -c "import pynput" 2>/dev/null; then
  "$ROOT/.venv/bin/pip" install --quiet pynput 2>/dev/null \
    || echo "NOTE: pynput did not install (needs gcc + python3-dev); the global shortcut is off."
fi

# 3) CLI wrapper on PATH ----------------------------------------------------
mkdir -p "$BIN"
# PYTHONPATH pins the wrapper to THIS clone, so it keeps working from any
# working directory even if a copy of deskglow is also installed elsewhere.
cat > "$BIN/deskglow" <<EOF
#!/bin/sh
export PYTHONPATH="$ROOT\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$PY" -m deskglow "\$@"
EOF
chmod +x "$BIN/deskglow"
echo "installed CLI -> $BIN/deskglow"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "NOTE: $BIN is not on your PATH; add it to your shell rc." ;;
esac

# 4) start at login ---------------------------------------------------------
# Linux: the systemd --user unit (text from deskglow.drivers.systemd, the same
# one the desktop app's "start at login" writes), or an XDG autostart entry if
# there is no systemd user manager. macOS: a LaunchAgent (launchctl).
if [ "$OS" = "Darwin" ]; then
  "$PY" -c "from deskglow.app.wiring import build_services as b; b().autostart.set_enabled(True)" \
    && echo "installed + loaded LaunchAgent ~/Library/LaunchAgents/io.deskglow.daemon.plist"
elif systemctl --user show-environment >/dev/null 2>&1; then
  mkdir -p "$UNIT_DIR"
  # drop the old enablement first: earlier versions installed into default.target
  systemctl --user disable deskglowd.service >/dev/null 2>&1 || true
  "$PY" -c "import sys; from deskglow.drivers.systemd import unit_text; sys.stdout.write(unit_text(sys.argv[1]))" \
    "$PY" > "$UNIT_DIR/deskglowd.service"
  echo "installed unit -> $UNIT_DIR/deskglowd.service"
  systemctl --user daemon-reload
  systemctl --user enable --now deskglowd.service
  echo "enabled + started deskglowd.service"
  systemctl --user --no-pager status deskglowd.service | head -5 || true
else
  "$PY" -c "from deskglow.drivers.xdg_autostart import XdgAutostart as X; X(executable='$PY').set_enabled(True)"
  echo "systemd --user is unavailable: added ~/.config/autostart/deskglowd.desktop instead."
  echo "The daemon starts at your next login (or on the first 'deskglow' command)."
fi

echo
echo "=================================================="
echo "  Installed! Last step: find your LED strip."
echo "=================================================="
echo "Make sure the strip is plugged in, close by, and the phone app is CLOSED."
echo

# offer to run the guided device setup now (only if we have a terminal)
if [ -t 0 ] && [ -z "${DESKGLOW_NO_SETUP:-}" ]; then
  printf "Find your strip now? [Y/n] "
  read -r ans || ans=""
  case "$ans" in
    [Nn]*) echo "Skipped. Run it later with:  deskglow setup" ;;
    *)     "$BIN/deskglow" setup || echo "Setup didn't complete — run 'deskglow setup' when ready." ;;
  esac
else
  echo "Run:  deskglow setup"
fi

echo
echo "After setup, use the CLI:"
echo "   deskglow on        deskglow color blue        deskglow screen        deskglow off"
