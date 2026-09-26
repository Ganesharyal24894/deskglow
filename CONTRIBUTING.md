# Contributing to Deskglow

Thanks for wanting to help. This is a small project with a simple shape, so the
contribution rules are short — but the one about **bug fixes being test-first**
is not optional. Please read that section before you open a PR.

---

## Local development setup

You need Python 3.9 or newer. BlueZ (`bluez`) is only needed if you want to
drive a real strip; it is **not** needed to run the tests.

```bash
git clone https://github.com/OWNER/deskglow
cd deskglow

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -e '.[dev]'
```

The `dev` extra pulls in pytest, pytest-asyncio, pytest-cov and ruff, plus the
optional runtime deps (`mss`, `numpy`, `python-xlib`) so screen- and audio-mode
code is importable while you work on it.

An editable install puts the `deskglow` and `deskglowd` entry points on your
PATH pointing at your working tree, so your edits take effect immediately.

> If you want the `systemd --user` service as well, run `./install.sh` from the
> clone. That is the end-user path; you don't need it just to write code.

## The one command that must pass

```bash
python scripts/check.py
```

It runs every check — the 200-line limit, the layer allow-list, preset
freshness, ruff and pytest — and fails if any of them fail. Work is not done
until it passes. The individual steps are below.

## Running the tests

```bash
python -m pytest -q
```

To run one file, one test, or with coverage:

```bash
python -m pytest tests/controller/test_daemon_race.py -q
python -m pytest -q -k "reconnect"
python -m pytest -q --cov=deskglow --cov-report=term-missing
```

### Tests must never require real hardware

This is a hard rule. The suite has to pass on a CI runner with **no Bluetooth
adapter, no X server, no audio device and no LED strip attached**, and it does
today. Anyone should be able to check out the repo and get a green run in
seconds.

So: fake the edges. Controllers only ever see the interfaces in
`deskglow/services/`, and `tests/fakes.py` has fakes for all of them (a fake
device, storage, scanner, IPC client, process control...). Write controller and
view tests against those; test a driver by injecting a fake for the library it
wraps (every driver takes its factory/`run`/`popen` as a parameter). Don't
`sleep()` waiting for real timing; drive the clock yourself.

If a test genuinely cannot work without a strip in the room, mark it:

```python
@pytest.mark.hardware
def test_strip_actually_lights_up():
    ...
```

`hardware` is a registered marker, and CI runs `pytest -m "not hardware"`, so
marked tests are skipped there. Treat this as an escape hatch of last resort —
a hardware-marked test is a test that will effectively never run.

## Running the linter

```bash
ruff check .
ruff check . --fix     # apply the safe autofixes
```

Configuration lives in `pyproject.toml` (line length 100, target py39, rule set
`E,F,W,B,UP,C4,SIM`). The one exception is `tools/`, which has its own
`tools/ruff.toml` relaxing the style rules — those are historical
reverse-engineering scripts, not maintained code (see `tools/README.md`).

Please don't reformat code you aren't otherwise changing; it makes review
harder and buries the actual fix.

---

## Project layout

```
deskglow/           the installed package (layered; see docs/ARCHITECTURE.md)
  model/            colours, settings schema + validation, generated presets
  services/         interfaces (typing.Protocol) the controllers depend on
  controller/       connection policy, daemon, commands, modes, discovery, client
  view/             the CLI and the strip frame encoder
  drivers/          Linux implementations (bleak/BlueZ, mss, Xlib, PipeWire,
                    unix socket, ~/.config, systemd)
  app/              entry points and driver wiring
presets/            per-controller presets (JSON) -> deskglow/model/presets_gen.py
scripts/            check.py, check_lines.py, check_layers.py (+ layers.json),
                    gen_presets.py
tests/              the offline test suite, mirroring the package layers
tools/              protocol-exploration scripts, kept for reference only
```

Two rules are enforced by `scripts/check.py`:

- **No `.py` file over 200 lines** in `deskglow/`, `tests/`, `scripts/` or
  `tools/`. Split by responsibility.
- **Layering.** `scripts/layers.json` is an allow-list of what each layer may
  import. Controllers, views, the model and services never import drivers or
  OS/hardware libraries (`bleak`, `mss`, `Xlib`, `subprocess`, `os`, `socket`...);
  only `drivers/` does, and only `app/` wires drivers in. Changing `layers.json`
  is an architecture decision and needs a reason in the PR.

The important architectural idea: **only the daemon touches Bluetooth.**

- **`controller/daemon.py`** (+ `lifecycle.py`, `commands.py`) is the
  `deskglowd` service. It owns the one and only strip link, runs exactly one
  mode at a time, and answers requests over the `IpcServer` service (a unix
  socket on Linux). It also handles reconnection, dead-link detection and
  releasing the radio when the strip is off.
- **`view/cli.py`** is the `deskglow` command. It is a *thin client*: it parses
  arguments, sends one JSON request to the daemon, prints the reply. It will
  auto-start the daemon (`controller/client.py`) if it isn't running.
- **`controller/device.py`** and **`connect.py`** are the connection policy the
  daemon sits on: hold at most one connection, reconnect transparently, back
  off, verify the link, and be a good neighbour to other Bluetooth devices —
  all expressed against the `LightLink` service. BlueZ specifics live in
  `drivers/ble_bleak.py` and `drivers/bluez.py`.
- **`controller/modes/`** is one module per behaviour — `solid`, `screen`,
  `calm`, `circadian`, `patterns`, `pomodoro`, `audio` — each a `Mode` subclass
  driven by the `ModeContext` in `modes/base.py`. `modes/__init__.py` is the
  registry. A mode never opens a connection itself; it asks the context to set a
  colour, and gets screen/audio capture from the context's services.

If you're adding a behaviour, it almost certainly belongs in
`controller/modes/`, gets registered in `modes/__init__.py`, and needs a CLI
subcommand in `view/cli_parser.py`.

### Adding a controller preset

Everything controller-specific — how to recognise it in a scan, its GATT
UUIDs, the byte template of every command, value ranges and the built-in effect
table — is data in `presets/controllers/<id>.json`. After editing or adding one,
run `python scripts/gen_presets.py` and commit the regenerated
`deskglow/model/presets_gen.py` (`scripts/check.py` fails if it is stale, and the
wheel build regenerates it).

### Porting to another OS

Add driver modules under `deskglow/drivers/` implementing the interfaces in
`deskglow/services/`, and one builder in `deskglow/app/wiring.py`. Model,
services, controller and view code should not need to change.

---

## Bug-fixing workflow: test first, strictly

When you fix a bug in this project, do it in this order. Not "usually" — always.

1. **Reproduce the bug in a test.** Before touching the implementation, write a
   test that exercises the broken behaviour and asserts the *correct* result.
2. **Run it and watch it fail.** This is the step people skip, and it is the
   whole point. A test that passes before your fix is not testing your fix — it
   proves nothing, and it will not stop the bug coming back. If it passes
   immediately, you have not reproduced the bug yet; go back to step 1.
3. **Now write the fix.** Change as little as needed to make that test pass.
4. **Re-run the suite.** Confirm two things: your new test now passes, *and*
   nothing else broke (`python scripts/check.py`).

**A PR that fixes a bug must include the regression test.** A fix without a test
that would have caught it will be asked to add one before it is merged. If you
believe a bug is genuinely untestable without hardware, say so explicitly in the
PR and explain why — but look hard for a seam first: most of the bugs found in
this project so far (connection races, mode-switch races, stale-link detection)
were reproducible with a fake BLE client and a controlled clock.

Please also mention the fix under `## [Unreleased]` in `CHANGELOG.md`.

---

## Pull requests

- Branch off `main`.
- Keep PRs focused; unrelated cleanups belong in their own PR.
- Fill in the PR template, including the regression-test checkbox.
- Don't add a **runtime** dependency without discussing it in an issue first.
  The core install is deliberately just `bleak`; anything else belongs in an
  optional extra (`screen`, `audio`) so a CLI-only user doesn't pay for it.
- Don't commit anything strip-specific: no MAC addresses, no personal config.

## Reporting bugs

Open an issue with the bug report template and fill in every field — especially
`deskglow status`, your strip's advertised name, and the
`journalctl --user -u deskglowd.service` output. Connection problems are basically
undiagnosable without them.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
