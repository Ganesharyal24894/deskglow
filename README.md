# Light — control your Bluetooth LED strip

Turn a cheap Bluetooth RGB LED strip into a smart **monitor backlight** and mood
light for your Linux desktop:

- 🖥️ **Screen mode** — the strip matches the colors on your screen (bias light)
- 🌈 **Patterns** — the strip's built-in effects (jump / fade / blink), like the phone app
- 🕯️ **Calm / Circadian** — gentle color drift, or white that warms up in the evening
- 🎵 **Audio** — the strip pulses to your music (system sound or microphone)
- 🎨 **Any color + brightness**, from a simple app or one-word commands

It runs quietly in the background and starts automatically when you log in.

**Works with** the common Bluetooth RGB strips whose phone app is *Lotus Lantern
/ iDeal LED / LED BLE* and whose controller shows up as **`MELK-…`**, **`ELK-…`**,
or **`LEDBLE-…`** (the ELK-BLEDOM protocol).

---

## Install (one command)

Open a terminal in this folder and run:

```bash
./install.sh
```

That's it. The installer will:
1. Install the bits it needs (asks for your password **once**),
2. Set up the **Light** app and the `sc295` command,
3. Offer to **find your strip**.

> Downloaded a ZIP? Unzip it, right-click the folder → *Open in Terminal*, then
> run `./install.sh`.

### Find your strip

If you skipped it during install, just plug the strip in, keep it nearby, close
the phone app, and either:

- open the **Light** app and click **“Find strip”**, or
- run `sc295 setup`

It scans, picks your strip, and flashes it **white** to confirm. Done — you never
need to know any Bluetooth addresses.

---

## Using it

### The app

Search your apps for **“Light”** and open it. Three tabs:

- **Main** — On / Off, colors, brightness, and Screen / Calm / Circadian / Audio
- **Patterns** — the built-in effects with a speed slider
- **Utility** — a Pomodoro focus timer

### Command line (optional)

```bash
sc295 on                 # warm white
sc295 off
sc295 color blue         # a name, ff8800 (hex), or "255 128 0"
sc295 brightness 60      # 0–100
sc295 screen             # match the screen (add: vivid | average | dominant | edge)
sc295 calm               # relaxing color drift
sc295 circadian          # cool by day, warm at night
sc295 pattern fade-colors --speed 40
sc295 audio --source mic # or --source system
sc295 status
```

---

## Troubleshooting

- **“No strip set up / not found”** → make sure the strip is powered, close to the
  PC, the **phone app is closed** (it can hold the connection), and Bluetooth is on.
  Then run `sc295 setup` again.
- **Colors flicker at high brightness** → your power adapter is too small for the
  strip length. Use a bigger one (e.g. a 5 V strip that's several meters long wants
  ~30 W+). This is a power issue, not the app.
- **App stuck on “connecting…”** → the strip probably dropped off; it reconnects on
  its own within a minute. If it doesn't, run `sc295 status`, or restart the
  service: `systemctl --user restart sc295d`.
- **Screen mode does nothing** → screen mode needs an X11 session (the default on
  most setups). It won't capture on a Wayland session.

---

## Uninstall

```bash
./uninstall.sh
```

Removes the app, command, service, and icon. Your strip is untouched.

---

## How it works (for the curious)

- A small **background service** (`systemd --user`) holds the Bluetooth link and
  runs one mode at a time. The **app** and the **`sc295`** command are thin clients
  that talk to it over a local socket — so commands are instant and there's only
  ever one Bluetooth connection.
- Protocol: **ELK-BLEDOM** (`7E … EF` frames) on characteristic `fff3`.
- Code lives in `sc295/` (`daemon`, `cli`, `gui`, `device`, `modes/`). It's plain
  Python + Tkinter with a few libraries (see `requirements.txt`); nothing is
  pip-installed system-wide — it all lives in a local `.venv`.
- `discover.py`, `probe.py`, `sc295.py` are low-level tools kept from reverse-
  engineering the protocol.
