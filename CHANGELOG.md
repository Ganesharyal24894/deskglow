# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Renamed to Deskglow.** The package is now `deskglow`, the commands are
  `deskglow` (CLI, also `python -m deskglow`) and `deskglowd` (daemon), the
  service is `deskglowd.service`, the socket is `deskglowd.sock`, settings live
  in `~/.config/deskglow`, and the address override is `DESKGLOW_ADDRESS`
  (was `SC295_ADDRESS`). On first run an existing `~/.config/sc295` is copied
  across (config and state), so the configured strip and last mode survive the
  upgrade. `install.sh` stops, disables and removes the old `sc295d.service` and
  the old `sc295` / `sc295-gui` launchers.
- **Restructured into layers** (`model`, `services`, `controller`, `view`,
  `drivers`, `app`; see `docs/ARCHITECTURE.md`). Controllers depend only on
  service interfaces; everything that touches BlueZ, X11, PipeWire, sockets,
  files or systemd is a Linux driver chosen in `deskglow/app/wiring.py`, so
  other platforms can be added without touching the core. Import rules are
  enforced by `scripts/check_layers.py`, and no source or test file may exceed
  200 lines (`scripts/check_lines.py`). Behaviour is unchanged.
- **Controller presets.** Everything specific to the ELK-BLEDOM controller —
  scan match rules, GATT UUIDs, the byte template of every command, value
  ranges and the built-in effect table — moved from code into
  `presets/controllers/elk-bledom.json`. `scripts/gen_presets.py` validates the
  presets and generates `deskglow/model/presets_gen.py` (a wheel build
  regenerates it; `--check` fails CI when it is stale). The frames sent to the
  strip are byte-for-byte identical to before.

### Removed

- The Tkinter GUI (`sc295-gui`, the "Light" app, its launcher and icon install).
  A new desktop app is planned; use the CLI meanwhile.
- `requirements.txt` (`pyproject.toml` declares every dependency).
- `tools/sc295.py`, the original single-file prototype (it remains in the git
  history); the other `tools/` scripts no longer hard-code a MAC address.

### Fixed

- **The strip flickered between two colours.** Overlapping mode changes (fast
  clicks in the app, or the GUI's `reload` + `set_mode` pair) each started a
  mode while the losing one kept running unreferenced, so two mode loops drove
  the strip at once and it alternated between their colours. Mode transitions
  are now serialised, a superseded mode refuses to write, and a mode that is slow
  to stop is reaped instead of being forgotten.
- **A core install could not run at all.** `sc295.modes` imported `numpy`, `mss`
  and `python-xlib` eagerly, so `pip install sc295` without the optional extras
  broke both the CLI and the daemon. Those modes are now imported on demand and
  a missing extra reports which one to install.
- **Two Bluetooth resource leaks.** A failed GATT write and a failed post-connect
  pin write both dropped a still-connected client without disconnecting it,
  leaking a system D-Bus connection each time — the failure mode that eventually
  breaks all Bluetooth on the machine.
- **`sc295 monitor` only accepted one developer's display names**
  (`HDMI-0`/`eDP-1-1`); it now takes any `xrandr` output name.
- **`sc295 restart-daemon` stopped the daemon for good**: it exits cleanly, and
  the unit's `Restart=on-failure` policy never brought it back. The unit now uses
  `Restart=always` and the command verifies a daemon is running afterwards.
- **A bad `max_brightness` killed the running mode.** Values are validated and
  clamped at the IPC boundary, and the brightness ceiling is applied defensively.
- **Messages over 64 KiB were unreadable** and a connection that closed
  mid-message raised inside the daemon's connection handler; malformed input now
  gets an error reply instead of a dropped connection.
- **A device advertising no RSSI aborted the whole scan**, so `sc295 setup` found
  nothing at all.
- **`sc295 color 08 10 20` failed** — zero-padded decimals are now accepted.
- **Solid mode blinked off between colours**: the fade started from black instead
  of the colour currently lit.
- Persisted state no longer shares a mutable default dict across loads; the
  daemon socket is created without a world-readable window; background tasks are
  strongly referenced and cancelled on shutdown; `sc295 repair` reports a missing
  `bluetoothctl` instead of a traceback; the GUI no longer stacks up overlapping
  status requests; and `status` reports the mode it is starting rather than
  claiming to be off during a slow connect.

### Added

- **Desktop app** (`deskglow-gui`, `pip install 'deskglow[gui]'`): a PySide6 app
  built to the approved design — Home (power, reset, glowing strip preview,
  brightness, hue ring, favourite swatches, mode tiles), Effects (all built-in
  effects with previews, filter, speed), Sync (screen sync with a diagram of the
  real monitors, colour styles and live colour/fps; music sync with a level
  meter, input and sensitivity), Focus (ring timer with pause/stop and
  steppers), Settings, a first-run Setup that scans through the daemon, and a
  tray quick panel. It never touches Bluetooth: every action is a request to
  the daemon, sent from a worker thread; status is polled every 2 s without
  overlapping requests. Closing the window keeps it in the tray when "Keep
  running in the tray" is on. Only the dark theme exists so far; the Theme
  setting resolves through a palette registry so a light palette can be added.
- **Daemon commands** for the app: `on` (resume what was lit before `off`),
  `toggle`, `scan`, `set_address`, `forget`, `monitors`, `favourite_add`,
  `favourite_remove`, `focus_pause`. `status` now also reports the strip
  colour, name, favourites, RSSI (when a scan saw it), live screen colour/fps,
  audio level, the focus timer, and whether sunset scheduling is available.
- **Settings**: `brightness` (a level under the `max_brightness` cap),
  `strip_name`, `favourites`, `sunset_on`, `audio_sensitivity` (the music
  mode's gain), `hotkey_on`, `tray_on`, `theme`, `focus_timer`.
- **Turn on at sunset**: the daemon computes local sunset (NOAA algorithm) from
  the time-zone position and lights the last solid colour if the strip is off.
- **Global shortcut** Ctrl+Alt+L toggles the strip (where the desktop allows it).
- CLI: `deskglow toggle`, `forget`, `name`, `sunset on|off`,
  `favourite add|remove`, `autostart on|off|status`. Setup now also saves the
  strip's advertised name next to its address.
- `tools/gui_screenshots.py` renders every screen offscreen for review.
- The focus timer's cyan is now #28A0C8 (matching the app's legend).

- `sc295 --version`.
- A test suite (`tests/`, ~800 tests) that runs fully offline and headless, plus
  GitHub Actions CI running ruff and pytest on Python 3.9-3.13 and checking that
  the package builds.
- Packaging via `pyproject.toml` with `screen`, `audio` and `all` extras.
- **macOS, Windows 11 and Linux Wayland support** (driver layer only; model,
  controller and view code unchanged). Only Linux/X11 has been used with a
  real strip so far; the new drivers are unit-tested with fake OS APIs.
  - Per-OS wiring in `deskglow/app/wiring.py` (linux X11 / Wayland, darwin,
    win32), importing each OS's drivers lazily.
  - Storage via `platformdirs` everywhere (Linux stays `~/.config/deskglow`,
    with the sc295 migration); `platformdirs` is now a core dependency.
  - IPC: unix socket on macOS in a private (0700) runtime dir; on Windows a
    loopback TCP server on a random port whose clients must present a
    256-bit token from `%LOCALAPPDATA%\deskglow\deskglowd.json`.
  - Start at login: `Autostart.is_enabled/set_enabled` for the systemd user
    unit (now `WantedBy`/`PartOf=graphical-session.target`, with an XDG
    autostart fallback), a macOS LaunchAgent, and the Windows `Run` key
    (`pythonw.exe`); Windows spawns the daemon detached with no console.
  - Screen: `mss` on macOS and Windows (per-monitor DPI aware, `DISPLAYn`
    names); Wayland via the xdg-desktop-portal ScreenCast API (restore token
    saved as `wayland_restore_token`) and `gst-launch-1.0 pipewiresrc`.
  - Focus tracking on Windows (foreground window's monitor) and macOS
    (Quartz window list); none on Wayland.
  - Audio via `soundcard` on Windows (speaker loopback / mic) and macOS (mic;
    system audio needs a loopback device such as BlackHole), and as the Linux
    fallback when `pw-record` is missing.
  - Global shortcut driver on `pynput` (off on Wayland), and a time-zone based
    location hint (tz database `zone1970.tab` / `zone.tab`).
  - BlueZ bonds are now dropped over D-Bus (`Adapter1.RemoveDevice`), with
    `bluetoothctl` as the fallback. On macOS a strip whose saved address is
    not seen is found by its saved name.
  - The daemon logs to its log file when it has no stderr (`pythonw.exe`).
  - `install.sh`/`uninstall.sh` handle macOS (LaunchAgent), the Wayland
    GStreamer packages and the XDG autostart fallback; README documents
    per-OS install steps, permissions and caveats.
  - CI runs `scripts/check.py` on Ubuntu, macOS and Windows for Python
    3.10-3.13 and smoke-tests the built wheel on each OS.


## [0.1.0] - 2026-08-22

Initial release.

### Added

- **Background daemon** (`sc295.daemon`, shipped as a `systemd --user` unit
  `sc295d.service`) that owns the single BLE link to the strip, runs one mode at
  a time, and serves clients over a unix domain socket. It releases the radio
  after an idle timeout while the strip is off, so it plays nicely with other
  Bluetooth devices.
- **CLI** (`sc295`) — a thin client over that socket: `on`, `off`, `color`,
  `brightness`, `screen`, `calm`, `circadian`, `pattern`, `audio`, `pomodoro`,
  `status`, `setup` and `repair`. It auto-starts the daemon when needed.
- **GUI** (`sc295-gui`, the "Light" app) — a dependency-free Tkinter front end
  with Main / Patterns / Utility tabs, talking to the same socket.
- **Modes**:
  - `solid` — any color plus brightness, eased and held.
  - `screen` — bias light that follows the focused monitor
    (`vivid` / `average` / `dominant` / `edge` styles).
  - `calm` — slow drift through a low-saturation palette with a breathing
    brightness envelope.
  - `circadian` — colour temperature and brightness tracking the time of day.
  - `pattern` — the controller's own built-in hardware effects (jump / fade /
    blink) with a speed control.
  - `pomodoro` — a focus timer signalled through the strip's color.
  - `audio` — brightness reacting to system output or microphone level, captured
    via PipeWire's `pw-record`.
- **ELK-BLEDOM protocol support** (`sc295.protocol`): 9-byte `7E … EF` frames
  written to characteristic `fff3`, covering power, colour, brightness, effect
  selection and effect speed.
- **Guided setup** (`sc295 setup` / "Find strip") that scans for MELK- / ELK- /
  LEDBLE-style controllers and flashes the chosen strip white to confirm, so
  users never need to know a Bluetooth address.
- **Dead-link detection and `sc295 repair`**, which resets the Bluetooth adapter
  and reconnects when the GATT link goes stale.
- `install.sh` / `uninstall.sh` for a from-source install of the app, CLI,
  service and desktop icon.

[Unreleased]: https://github.com/Ganesharyal24894/deskglow/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ganesharyal24894/deskglow/releases/tag/v0.1.0
