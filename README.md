# sc295 — LED strip control

A background daemon + CLI for the **MELK-OA10 / SC295** BLE LED strip
(`BE:69:4C:0F:1E:2F`). The daemon holds the Bluetooth connection and runs one
"mode" at a time; the `sc295` CLI just sends it instant commands over a local
socket. No manual connect/disconnect, and it stays out of the way of other
Bluetooth devices (e.g. a speaker) — it never keeps scanning and releases the
radio when the strip is off.

## Install

```bash
./install.sh
```

This sets up the venv + deps, installs `~/.local/bin/sc295`, and enables a
`systemd --user` service so the daemon auto-starts on login and restarts on
failure.

## Usage

```bash
sc295 on                 # warm white
sc295 off                # turn off (and release the BT radio after ~30s)
sc295 color blue         # solid color: name, #rrggbb, or "R G B"
sc295 color 255 128 0
sc295 brightness 60      # global brightness ceiling (0-100)
sc295 status             # what's running

# modes
sc295 screen             # bias light: average color of the FOCUSED monitor
sc295 monitor HDMI-0     # or: focus (default) | eDP-1-1 | both
sc295 calm               # eye-pleasing colors that drift + gently breathe
sc295 circadian          # cool by day, warm at night, automatically
sc295 pattern fade-colors --speed 40   # built-in effect (Lotus-style)
sc295 patterns           # list them (jump/fade/blink variants)
sc295 pomodoro --work 25 --break 5 --rounds 4   # focus timer, shown in color
sc295 audio              # brightness reacts to your PC's audio output
```

## GUI

```bash
sc295-gui        # or launch "sc295 LED" from your app menu
```

A small tabbed Tkinter window (zero extra dependencies) with a shared live
connection dot at the top:

- **Main** — On/Off/Reset, color presets + custom picker, brightness slider,
  and the ambient modes (Screen with style + monitor, Calm, Circadian, Audio
  with system/mic source).
- **Patterns** — the controller's built-in effects (jump / fade / blink, same
  set as the Lotus Lantern app) with a speed slider.
- **Utility** — Pomodoro (work / break / rounds); room for more later.

It drives the same daemon over the socket — no separate Bluetooth logic.

## How it works

- **Protocol**: ELK-BLEDOM (`7E .. EF` frames) on characteristic `fff3`.
- **Modes** modulate brightness by scaling RGB (device brightness pinned at
  100), so transitions and breathing are smooth.
- **Connection**: on drop it reconnects scan-free first (no speaker
  interference), falling back to a short scan; a stale BlueZ *bond* is dropped
  automatically if it blocks service resolution.

## Files

- `sc295/` — package: `protocol`, `color`, `device`, `daemon`, `cli`, `modes/`
- `probe.py`, `discover.py` — low-level BLE probes used while reverse-engineering
- `sc295.py` — the earlier standalone single-file tool (still works; includes the
  `sweep`/`soak` flicker diagnostics)

## Debugging the flicker

The full-brightness flicker did **not** reproduce from this tool (a clean,
rate-limited command stream); it appears to be something the phone app does
(likely a music/mic-reactive mode or command spamming). If it recurs, reproduce
with the standalone diagnostics:

```bash
.venv/bin/python sc295.py soak white --seconds 120   # sustained max-current hold
.venv/bin/python sc295.py sweep blue                 # find a brightness threshold
```
