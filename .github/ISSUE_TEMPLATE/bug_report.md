---
name: Bug report
about: Something doesn't work — colors, connection, a mode, the daemon or the CLI
title: ''
labels: bug
assignees: ''
---

## What happened

<!-- What did you do, what did you expect, and what happened instead? -->

## Steps to reproduce

1.
2.
3.

## Environment

Please fill all of these in — connection bugs are almost impossible to diagnose
without them.

- **Linux distribution and version:** <!-- e.g. Ubuntu 24.04, Fedora 40, Arch -->
- **Desktop session:** <!-- X11 or Wayland; needed for screen mode bugs -->
- **Python version:** <!-- output of `python3 --version` -->
- **Deskglow version / install method:** <!-- `deskglow --version`; via ./install.sh, or pip -->
- **BlueZ version:** <!-- output of `bluetoothd --version`, if you have it -->

## `deskglow status`

```
paste the full output of `deskglow status` here
```

## Your strip's advertised name

The name the controller advertises over Bluetooth — e.g. `MELK-OA10`, `ELK-BLEDOM`,
`LEDBLE-…`. You can get it from `deskglow setup`, or with
`bluetoothctl scan on` / `bluetoothctl devices`.

```
paste it here
```

## Daemon log

```
paste the output of:  journalctl --user -u deskglowd.service -n 200 --no-pager
```

## Anything else

<!-- Screenshots, a video of the strip misbehaving, what you already tried. -->

<!--
Two quick checks that resolve most connection reports:
  * Is the phone app (Lotus Lantern / iDeal LED / LED BLE) closed? It holds the link.
  * Is the strip paired/bonded in bluetoothctl? It must NOT be — bonding breaks
    GATT service resolution on BlueZ. `bluetoothctl remove <MAC>` and retry.
-->
