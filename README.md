# Deskglow — control your Bluetooth LED strip

**A desktop controller for cheap ELK-BLEDOM Bluetooth RGB LED strips — screen
bias light, ambient modes, a CLI, and a background service that holds the
connection.**

> Deskglow was previously called **sc295**. Upgrading keeps your settings: on
> first run `~/.config/sc295` is copied to `~/.config/deskglow`, and
> `./install.sh` retires the old `sc295d.service` and `sc295` command.

Turn a cheap Bluetooth RGB LED strip into a smart **monitor backlight** and mood
light for your desktop — Linux, macOS or Windows:

- 🖥️ **Screen mode** — the strip matches the colors on your screen (bias light)
- 🌈 **Patterns** — the strip's built-in effects (jump / fade / blink), like the phone app
- 🕯️ **Calm / Circadian** — gentle color drift, or white that warms up in the evening
- 🎵 **Audio** — the strip pulses to your music (system sound or microphone)
- 🎨 **Any color + brightness**, from one-word commands

It runs quietly in the background and starts automatically when you log in.

**Works with** the common Bluetooth RGB strips whose phone app is *Lotus Lantern
/ iDeal LED / LED BLE* and whose controller shows up as **`MELK-…`**, **`ELK-…`**,
or **`LEDBLE-…`** (the ELK-BLEDOM protocol). See
[Hardware compatibility](#hardware-compatibility).

---

## Supported platforms

Deskglow runs on **Linux (X11 and Wayland), macOS and Windows 11**, with Python
**3.10 or newer**. The core (BLE control, patterns, calm, circadian, pomodoro,
CLI, daemon) is the same everywhere; what differs is how each OS lets us see
the screen, hear the audio and start at login.

> **Honest status.** Only **Linux / X11** has been used with a real strip.
> The macOS, Windows and Wayland drivers are new: every one of them is covered
> by unit tests (with fake OS APIs) and CI runs the suite on all three OSes,
> but none has yet been exercised end-to-end on a real Mac, a real Windows PC
> or a live Wayland session. Please report what you find.

| Feature | Linux X11 | Linux Wayland | macOS | Windows 11 |
| --- | --- | --- | --- | --- |
| Bluetooth control (bleak) | BlueZ — **tested** (new D-Bus bond removal: untested live) | BlueZ — as X11 | CoreBluetooth — untested | WinRT — untested |
| Screen mode | `mss` + `xrandr` — **tested** | xdg-desktop-portal + GStreamer — untested | `mss` — untested | `mss`, DPI-aware — untested |
| Follows the focused window | yes | **no** (uses the monitor you shared) | yes | yes |
| Audio: system sound | PipeWire `pw-record` — **tested** (`soundcard` fallback untested) | same | **no** without BlackHole | WASAPI loopback |
| Audio: microphone | yes | yes | yes | yes |
| Start at login | systemd user unit (fallback: XDG autostart) | same | LaunchAgent | `HKCU\…\Run` entry |
| Global shortcut (desktop app) | `pynput` (optional, see below) | **no** | `pynput` + Accessibility | `pynput` |
| `deskglow repair` adapter reset | yes (`bluetoothctl`) | yes | no — toggle Bluetooth yourself | no — toggle Bluetooth yourself |
| Sunset times (circadian) | from the time zone | same | same | same (`tzlocal`) |

**Desktop app:** Not in this release: the old Tkinter app was removed and a new cross-platform app is planned. Use the CLI.

### Caveats and permissions per OS

**Linux / X11**
- Needs **BlueZ**. Do not pair the strip (see [Hardware compatibility](#hardware-compatibility)).
- The global shortcut uses `pynput`, which needs `evdev` compiled from source;
  it is therefore *not* installed automatically on Linux. `pip install pynput`
  (with `gcc` and `python3-dev` present) turns it on.

**Linux / Wayland**
- The first time screen mode starts, your desktop shows a **one-time
  screen-share dialog**: pick the monitor behind the strip. Deskglow saves the
  portal's restore token, so later starts skip the dialog (until you revoke it).
- Needs the **GStreamer PipeWire plugin** and `gst-launch-1.0`:
  `sudo apt install gstreamer1.0-tools gstreamer1.0-pipewire` (Debian/Ubuntu),
  `gstreamer1-plugins-base-tools gstreamer1-plugin-pipewire` (Fedora),
  `gstreamer gst-plugin-pipewire` (Arch). Also `xdg-desktop-portal` plus your
  desktop's backend (GNOME, KDE and wlroots ship one).
- **No focused-window tracking** (Wayland does not reveal window positions):
  screen mode always samples the monitor you shared.
- **Global shortcuts are unavailable** (Wayland does not let apps grab keys).

**macOS**
- **Bluetooth permission**: when you run `deskglow` from a terminal, macOS
  attributes Bluetooth access to the terminal app (Terminal, iTerm…), so allow
  it there when asked. The login daemon (LaunchAgent) runs `python` directly;
  if it cannot see the strip, allow Bluetooth for that Python in *System
  Settings → Privacy & Security → Bluetooth*.
- **Screen Recording**: screen mode triggers the *Screen Recording* prompt.
  On macOS 15 Sequoia the system asks you to **re-confirm this about once a
  month**. Without it macOS silently hands back only the wallpaper.
- **No system-audio capture**: macOS cannot record what the speakers play.
  Install a loopback device such as [BlackHole](https://github.com/ExistentialAudio/BlackHole),
  route your output through it and pick it as the audio target;
  `--source mic` works out of the box (Microphone permission).
- The global shortcut needs the **Accessibility** permission.
- Bluetooth addresses on macOS are per-Mac identifiers, not MAC addresses: run
  `deskglow setup` on each Mac. If the saved address is not seen, Deskglow
  falls back to the strip's saved name (when the config has one).

**Windows**
- **Windows 11** is the target. Windows 10 is *not officially supported* by
  current `bleak` releases; it may work, untested.
- The daemon listens on `127.0.0.1` on a random port and only answers clients
  that present the secret token stored in `%LOCALAPPDATA%\deskglow`.
- Future packaged (unsigned) builds will trigger a **SmartScreen** warning
  (*More info → Run anyway*); installing from source with `pip` does not.
- `deskglow repair` cannot reset the adapter: toggle Bluetooth off and on in
  *Settings → Bluetooth & devices*.

---

## Install

### From PyPI (once released)

> **Note:** `deskglow` is **not published to PyPI yet.** Until the first release
> lands, use the from-source steps below.
> These are the commands that will work once it is published:

```bash
pipx install deskglow            # isolated, recommended
# or
pip install 'deskglow[all]'      # everything, into the current environment
```

What the extras give you:

| Install | You get |
| --- | --- |
| `pip install deskglow` | The **core**: the `deskglow` CLI and the `deskglowd` background daemon — power, colors, brightness, patterns, calm, circadian, pomodoro. Dependencies: `bleak`, `platformdirs` (plus `tzlocal`/`tzdata` on Windows). |
| `pip install 'deskglow[screen]'` | Adds **screen mode**: `mss`, `numpy`, and `python-xlib` (Linux) or `pyobjc-framework-Quartz` (macOS). |
| `pip install 'deskglow[audio]'` | Adds **audio mode**: `numpy` and `soundcard`. On Linux, PipeWire's `pw-record` is used when present (from `pipewire` / `pipewire-utils`). |
| `pip install 'deskglow[all]'` | All of the above plus the desktop app extras. |

A pip install gives you the `deskglow` and `deskglowd` commands but does not
set up start-at-login; the from-source steps below do.

### Linux (from source: CLI + service)

```bash
git clone https://github.com/Ganesharyal24894/deskglow
cd deskglow
./install.sh
```

The installer will:
1. Install the system bits it needs (`bluez`, and on Wayland the GStreamer
   PipeWire packages; asks for your password **once**),
2. Create a `.venv` in the clone, install Deskglow into it, and put the
   `deskglow` command in `~/.local/bin`,
3. Install and start the `deskglowd` **systemd user service** (or, without a
   systemd user manager, an XDG autostart entry),
4. Offer to **find your strip**.

> Downloaded a ZIP? Unzip it, right-click the folder → *Open in Terminal*, then
> run `./install.sh`.

**Don't want it running `sudo apt-get`?** Set `DESKGLOW_NO_APT=1`. The installer
will print exactly which packages it wanted and let you install them yourself:

```bash
DESKGLOW_NO_APT=1 ./install.sh
```

(It prints the exact `apt-get` commands before running them either way, and
nothing else in the script needs root.)

### macOS (from source)

Needs Python 3.10+ (python.org or Homebrew). In Terminal:

```bash
git clone https://github.com/Ganesharyal24894/deskglow
cd deskglow
./install.sh
```

On macOS the installer skips system packages, creates the `.venv`, installs
the `deskglow` command into `~/.local/bin` and loads a **LaunchAgent**
(`~/Library/LaunchAgents/io.deskglow.daemon.plist`, logs in
`~/Library/Logs/deskglow/daemon.log`). Allow Bluetooth for Terminal when macOS
asks.

### Windows 11 (from source)

In PowerShell, with Python 3.10+ from python.org (tick *Add python.exe to PATH*):

```powershell
git clone https://github.com/Ganesharyal24894/deskglow
cd deskglow
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[all]"
# start the daemon at login (adds HKCU\...\Run\Deskglow, uses pythonw.exe)
.venv\Scripts\deskglow autostart on
.venv\Scripts\deskglow setup
```

Settings live in `%LOCALAPPDATA%\deskglow`, the daemon log in
`%LOCALAPPDATA%\deskglow\Logs\daemon.log`. To remove the login entry, run
`deskglow autostart off`.

### Find your strip

If you skipped it during install, just plug the strip in, keep it nearby, close
the phone app, and run `deskglow setup`.

It scans, picks your strip, and flashes it **white** to confirm. Done — you never
need to know any Bluetooth addresses.

---

## Using it

### Command line

```bash
deskglow on              # warm white
deskglow off
deskglow color blue         # a name, ff8800 (hex), or "255 128 0"
deskglow brightness 60      # 0–100
deskglow screen             # match the screen (add: vivid | average | dominant | edge)
deskglow calm               # relaxing color drift
deskglow circadian          # cool by day, warm at night
deskglow pattern fade-colors --speed 40
deskglow audio --source mic # or --source system
deskglow status
```

---

## Hardware compatibility

This talks the **ELK-BLEDOM** protocol: 9-byte `7E … EF` frames written to GATT
characteristic `fff3`.

**It should work with your strip if:**

- The controller advertises as **`MELK-…`**, **`ELK-…`**, `ELK-BLEDOM`, or
  **`LEDBLE-…`** (check with `deskglow setup`, or `bluetoothctl scan on`), **and**
- The phone app the strip shipped with is **Lotus Lantern**, **iDeal LED**, or
  **LED BLE**.

These are the generic RGB controllers sold under dozens of brand names; developed
and tested against a **MELK-OA10 / SC295**. Strips using other protocols (for
example the Triones `0x56…` family, or Bluetooth Mesh / Wi-Fi controllers) are
**not** supported.

> ### ⚠️ Do not pair or bond the strip in `bluetoothctl`
>
> These strips need no authentication — there is nothing to pair with. If you
> pair/bond one anyway, **BlueZ stops resolving its GATT services** and every
> connection attempt hangs or comes back with no characteristics.
>
> If you already paired it, remove the bond and let the tool connect on its own:
>
> ```bash
> bluetoothctl remove AA:BB:CC:DD:EE:FF
> ```
>
> `deskglow setup` and `deskglow repair` connect without bonding.

---

## Troubleshooting

- **“No strip set up / not found”** → make sure the strip is powered, close to the
  PC, the **phone app is closed** (it can hold the connection), and Bluetooth is on.
  Then run `deskglow setup` again.
- **Colors flicker at high brightness** → your power adapter is too small for the
  strip length. Use a bigger one (e.g. a 5 V strip that's several meters long wants
  ~30 W+). This is a power issue, not the app.
- **Stuck on “connecting…”, or shows connected but the strip won't respond**
  → run `deskglow repair`. It resets the Bluetooth adapter and reconnects. (The
  daemon also auto-detects a dead link within ~12s and reconnects on its own.)
- **Very dim brightness flickers** → cheap controllers have unstable PWM at very
  low levels; keep brightness above ~20% for a rock-steady color.
- **Screen mode does nothing** → on Wayland, check the GStreamer PipeWire plugin
  is installed and that you accepted the screen-share dialog; on macOS, allow
  *Screen Recording* for your terminal (or Python) and re-confirm it when
  Sequoia asks. The daemon log says what failed.

Still stuck? Open an issue — please include `deskglow status`, your strip's
advertised name, your OS, and the daemon log: `journalctl --user -u
deskglowd.service` (Linux), `~/Library/Logs/deskglow/daemon.log` (macOS) or
`%LOCALAPPDATA%\deskglow\Logs\daemon.log` (Windows).

---

## Uninstall

```bash
./uninstall.sh
```

Removes the command and the login service (systemd unit, XDG autostart entry
or macOS LaunchAgent, and any leftovers of the old sc295 install). Your
settings and your strip are untouched. On Windows, run `deskglow autostart off`
and delete the folder.

---

## How it works (for the curious)

- A small **background service** (`deskglowd`, started at login by `systemd
  --user`, a macOS LaunchAgent or the Windows Run key) holds
  the Bluetooth link and runs one mode at a time. The **`deskglow`** command is a
  thin client that talks to it over a local socket — so commands are instant and
  there's only ever one Bluetooth connection.
- Protocol: **ELK-BLEDOM** (`7E … EF` frames) on characteristic `fff3`. Everything
  controller-specific (match rules, GATT UUIDs, frame templates, the effect
  table) lives in a JSON preset, [`presets/controllers/elk-bledom.json`](presets/controllers/elk-bledom.json),
  from which `scripts/gen_presets.py` generates `deskglow/model/presets_gen.py`.
- Plain Python with very few dependencies: the core needs only `bleak` and
  `platformdirs`; screen/audio mode pull in `mss` / `numpy` / `soundcard` and a
  per-OS helper (`python-xlib`, `pyobjc-framework-Quartz`) via the optional extras.

The package is layered (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); the
import rules are enforced by `scripts/check_layers.py`):

```
deskglow/
  model/        colours, the settings schema, generated controller presets
  services/     interfaces: LightLink, Scanner, ScreenSource, FocusTracker,
                AudioSource, IpcServer/IpcClient, Storage, Autostart, ProcessControl
  controller/   connection policy, daemon + commands, every lighting mode,
                screen-colour reduction, discovery, the daemon client
  view/         the CLI, and the encoder that renders strip frames from a preset
  drivers/      per-OS implementations: bleak (BlueZ / CoreBluetooth / WinRT),
                mss + xrandr / Win32 / Quartz, xdg-desktop-portal + GStreamer
                (Wayland), PipeWire / soundcard audio, unix-socket or
                token-guarded TCP IPC, systemd / launchd / Run-key autostart,
                platformdirs storage
  app/          entry points (`deskglow`, `deskglowd`) and driver wiring
```

The low-level scripts used to reverse-engineer the protocol (`discover.py`,
`probe.py` and friends) live in
[`tools/`](tools/). They are kept for reference only and are not part of the
installed package — see [`tools/README.md`](tools/README.md).

---

## Development

Contributions welcome. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the dev
setup, how to run the tests and linter, a tour of the code, and the project's
**test-first bug-fixing workflow** — a PR that fixes a bug must include a
regression test that failed before the fix.

The quick version:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
python -m pytest -q
ruff check .
python scripts/check.py      # everything: lint, line limit, layers, presets, tests
```

The test suite is fully offline and headless: no Bluetooth adapter, no X server,
no audio device and no LED strip required.

Release notes live in [CHANGELOG.md](CHANGELOG.md).

---

## License

[MIT](LICENSE) © 2026 Ganesh Sharma
