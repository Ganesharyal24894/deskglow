# tools/ — protocol-exploration scripts

These are the throwaway scripts used to reverse-engineer the LED strip's
Bluetooth protocol before the `deskglow` package (then called `sc295`) existed.
They are kept **for reference only**:

- They are **not part of the installed package** — `pip install deskglow` does
  not ship them, and nothing in `deskglow/` imports them.
- They are **not maintained or tested**.
- They need your strip's MAC address: pass `--address AA:BB:CC:DD:EE:FF` (or
  `-a`), or set `DESKGLOW_ADDRESS`. Nothing is hard-coded (see `_address.py`).
- They talk to the strip **directly over BLE**, bypassing the daemon. Stop the
  daemon first (`systemctl --user stop deskglowd.service`) or they will fight it
  for the single BLE link.

Run them from a virtualenv that has `bleak` installed, e.g.
`python tools/discover.py --address AA:BB:CC:DD:EE:FF`.

## What each one does

| Script | Purpose |
| --- | --- |
| `discover.py` | Scans for the strip, connects, and dumps its full GATT table. This is what identified `fff3` as the write characteristic. Run this one first. |
| `conntest.py` | Smallest possible `bleak` connect loop — three attempts, then print the services/characteristics. Used to prove the link worked at all. |
| `conntest2.py` | Same idea via `bleak-retry-connector` (`establish_connection` + service cache), to see whether the retry helper worked around the BlueZ quirks. |
| `conntest3.py` | The recipe that turned out to be reliable: scan until the device is seen, **stop discovery**, then connect. |
| `probe.py` | Interactive frame probe. Connects once and writes arbitrary hex frames given on the command line (`python tools/probe.py -a AA:BB:CC:DD:EE:FF "7E 00 05 03 FF 00 00 00 EF"`), optionally listening on the `fff4` notify characteristic. This is how the frame layout was mapped out. |
| `prototest.py` | Fixed protocol smoke test: power on, then red / green / blue in sequence, using the scan → stop-discovery → connect recipe. |
| `reset_test.py` | Hunts for the frame that exits the button-induced effect/cycling mode, by trying candidate "reset to static" sequences that each end on a distinct solid color. |
| `reset_test2.py` | Follow-up to `reset_test.py`: forces static blue with with-response writes and then ramps brightness, to tell an effect-mode problem apart from a power brownout. |

| `_address.py` | Shared helper: where the scripts get the strip's address from. |

The original single-file CLI, `sc295.py` (power / color / brightness / effect /
raw / repl / monitor / fix-connection), used to live here too. It was the
ancestor of the package and was superseded by it; it has been removed and
remains available in the git history.

The protocol these scripts uncovered is now data — the controller preset
[`presets/controllers/elk-bledom.json`](../presets/controllers/elk-bledom.json) —
and is rendered, with tests, by [`deskglow/view/strip.py`](../deskglow/view/strip.py).
