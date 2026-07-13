#!/usr/bin/env bash
# Install the sc295 CLI (~/.local/bin/sc295) and the systemd --user daemon.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/.venv/bin/python"
BIN="$HOME/.local/bin"
UNIT_DIR="$HOME/.config/systemd/user"

echo "project root: $ROOT"

# 1) venv + deps ------------------------------------------------------------
if [ ! -x "$PY" ]; then
  echo "creating venv..."
  python3 -m venv "$ROOT/.venv"
fi
echo "installing python deps..."
"$ROOT/.venv/bin/pip" install --quiet --upgrade pip
"$ROOT/.venv/bin/pip" install --quiet bleak bleak-retry-connector mss numpy python-xlib

# 2) CLI wrapper on PATH ----------------------------------------------------
mkdir -p "$BIN"
# PYTHONPATH so the package imports from any working directory (the package is
# run from the source tree, not pip-installed).
cat > "$BIN/sc295" <<EOF
#!/bin/sh
export PYTHONPATH="$ROOT\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$PY" -m sc295 "\$@"
EOF
chmod +x "$BIN/sc295"
echo "installed CLI -> $BIN/sc295"

cat > "$BIN/sc295-gui" <<EOF
#!/bin/sh
export PYTHONPATH="$ROOT\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$PY" -m sc295.gui "\$@"
EOF
chmod +x "$BIN/sc295-gui"
echo "installed GUI -> $BIN/sc295-gui"

# app icon + launcher ("Light"), searchable from the app grid
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor"
mkdir -p "$APPS" "$ICONS/scalable/apps"
cp "$ROOT/icons/light.svg" "$ICONS/scalable/apps/sc295-light.svg"

# also render PNGs (for the titlebar/taskbar icon) if a converter is available
RASTER=""
command -v rsvg-convert >/dev/null && RASTER=rsvg
[ -z "$RASTER" ] && command -v inkscape >/dev/null && RASTER=inkscape
[ -z "$RASTER" ] && command -v convert >/dev/null && RASTER=convert
for s in 48 64 128 256; do
  mkdir -p "$ICONS/${s}x${s}/apps"
  out="$ICONS/${s}x${s}/apps/sc295-light.png"
  case "$RASTER" in
    rsvg)     rsvg-convert -w $s -h $s "$ROOT/icons/light.svg" -o "$out" 2>/dev/null ;;
    inkscape) inkscape -w $s -h $s "$ROOT/icons/light.svg" -o "$out" 2>/dev/null ;;
    convert)  convert -background none -resize ${s}x${s} "$ROOT/icons/light.svg" "$out" 2>/dev/null ;;
  esac
done

rm -f "$APPS/sc295.desktop"   # drop the old "sc295 LED" entry if present
cat > "$APPS/light.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Light
GenericName=LED Strip Control
Comment=Control the SC295 RGB LED strip
Exec=env PYTHONPATH=$ROOT $PY -m sc295.gui
Path=$ROOT
Icon=sc295-light
Terminal=false
Categories=Utility;
Keywords=led;light;rgb;strip;lamp;bluetooth;sc295;ambient;
StartupWMClass=Light
EOF
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f "$ICONS" 2>/dev/null || true
echo "installed launcher -> $APPS/light.desktop (name: Light)"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "NOTE: $BIN is not on your PATH; add it to your shell rc." ;;
esac

# 3) systemd --user service -------------------------------------------------
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/sc295d.service" <<EOF
[Unit]
Description=sc295 LED strip daemon
After=bluetooth.target graphical-session.target
Wants=bluetooth.target

[Service]
Type=simple
ExecStart=$PY -m sc295.daemon
WorkingDirectory=$ROOT
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
echo "installed unit -> $UNIT_DIR/sc295d.service"

if systemctl --user daemon-reload 2>/dev/null; then
  systemctl --user enable --now sc295d.service
  echo "enabled + started sc295d.service"
  systemctl --user --no-pager status sc295d.service | head -5 || true
else
  echo "systemctl --user unavailable here; start manually with:"
  echo "  systemctl --user enable --now sc295d.service"
fi

echo
echo "Done. Try:  sc295 status   |   sc295 screen   |   sc295 color blue"
