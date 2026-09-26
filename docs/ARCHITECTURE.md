# Deskglow architecture

Deskglow controls cheap Bluetooth LE RGB strips (ELK-BLEDOM family and
friends) from Linux, macOS and Windows. A background **daemon** owns the BLE
link and runs one lighting mode at a time; the **CLI** and the **desktop app**
are thin clients that talk to it over local IPC.

## Layers

```
deskglow/
  model/        data only: colours, settings schema, controller presets
  services/     interfaces (ports) the controllers depend on
  controller/   business logic: connection policy, daemon, modes, discovery
  view/         user-facing output: CLI, desktop app, strip frame encoding
  drivers/      the ONLY code that touches hardware, OS or radio libraries
  app/          composition root: picks drivers for this OS and wires them in
presets/        version-controlled per-controller presets (JSON)
scripts/        check.py (runs everything), line/layer checkers, preset generator
```

Dependency direction (an arrow means "may import"):

```
app ──► view ──► controller ──► services ──► model
 │                   │                         ▲
 └──► drivers ───────┴──► services, model ─────┘
```

- **model** — pure data and pure functions: colour maths, the settings schema
  and validation, the generated preset tables. No I/O, no asyncio.
- **services** — abstract interfaces (`typing.Protocol` / ABCs) plus small
  plain-data types: `LightLink` (connect / write / disconnect a strip),
  `Scanner`, `ScreenSource`, `FocusTracker`, `AudioSource`, `IpcServer` /
  `IpcClient`, `Storage` (config + state files), `Autostart` (run the daemon at
  login), `ProcessControl` (exit-for-restart, spawn the daemon). A `Services`
  container bundles the chosen implementations.
- **controller** — everything that decides *what* happens: the connection
  policy (backoff, keepalive, verify writes, de-dup, rate limiting), the daemon
  and its command handling, every lighting mode, screen-colour reduction
  algorithms, scan-result filtering. Controllers receive services by
  constructor injection and **never import drivers**.
- **view** — what a person or the strip sees: CLI argument parsing and output,
  the PySide6 desktop app, and the encoder that renders a light command into
  the bytes a controller preset describes.
- **drivers** — one module per platform integration: `bleak` BLE, BlueZ bond
  handling, `mss` screen grab, X11 / Win32 / macOS focus tracking, PipeWire /
  `soundcard` audio, unix-socket / TCP-loopback IPC, systemd / launchd /
  Windows autostart, per-OS paths.
- **app** — entry points (`deskglow`, `deskglowd`, `deskglow-gui`) and the
  wiring that chooses drivers from `sys.platform` and the environment.

Porting to a new OS or radio stack means adding driver modules and a line in
`app/` wiring. Model, services, controller and view code must not change.

## Enforced rules

`python scripts/check.py` runs every check and must pass before any work
counts as done. CI runs it on Linux, macOS and Windows.

1. **Line limit** — no `.py` file in `deskglow/`, `tests/`, `scripts/` or
   `tools/` may exceed 200 lines (`scripts/check_lines.py`). Split by
   responsibility.
2. **Layering** — `scripts/check_layers.py` parses every module with `ast`
   (including imports inside functions and `importlib.import_module("...")`
   calls with literal names) and checks each import against an **allow-list**
   in `scripts/layers.json`: per layer, the internal layers it may import and
   the stdlib / third-party top-level modules it may use. Anything not listed is
   an error, so a new library is caught without a rule change. Changing
   `layers.json` is an architecture decision and needs a reason in the PR.
3. **Presets** — controller presets live in `presets/controllers/*.json`.
   `scripts/gen_presets.py` validates them and generates
   `deskglow/model/presets_gen.py`; the wheel build regenerates it, and
   `check.py` fails if the checked-in copy is stale.
4. **Tests** — every behaviour has a host-only test (no BLE, display, audio
   device or network). A bug fix lands with a regression test that fails
   without the fix.
