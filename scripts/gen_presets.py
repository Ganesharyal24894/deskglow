#!/usr/bin/env python3
"""Validate presets/controllers/*.json and generate deskglow/model/presets_gen.py.

    python scripts/gen_presets.py            # (re)write the generated module
    python scripts/gen_presets.py --check    # exit 1 if the checked-in copy is stale

Stdlib only: this also runs from the wheel build hook (hatch_build.py).
Exit codes: 0 = ok, 1 = stale (--check), 2 = invalid preset.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESETS_DIR = ROOT / "presets" / "controllers"
OUT = ROOT / "deskglow" / "model" / "presets_gen.py"

HEADER = '''"""Controller presets — generated — do not edit.

Source: presets/controllers/*.json. Regenerate with `python scripts/gen_presets.py`.
Frames are tuples of byte values and placeholder names (see each preset's ranges).
"""

'''
KEYS = {"id", "name", "description", "match", "gatt", "ranges", "frames",
        "default_effect", "effects"}
OPTIONAL = {"description"}
# every frame a preset must describe -> the placeholders it must carry
FRAME_PARAMS = {
    "power_on": set(), "power_off": set(), "color": {"r", "g", "b"},
    "brightness": {"brightness"}, "effect": {"effect"}, "speed": {"speed"},
    "status_query": set(),
}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
BYTE_RE = re.compile(r"^[0-9A-Fa-f]{2}$")
PARAM_RE = re.compile(r"^\{([a-z_]+)\}$")


class PresetError(ValueError):
    """A preset file is malformed; the message names the file and the problem."""


def _need(cond, where, msg):
    if not cond:
        raise PresetError(f"{where}: {msg}")


def _uuid(value, where):
    _need(isinstance(value, str) and UUID_RE.match(value.lower()), where,
          f"not a 128-bit UUID: {value!r}")
    return value.lower()


def _int(value, where):
    """An int, or a '0x..' string (JSON has no hex literals)."""
    if isinstance(value, str) and re.match(r"^0[xX][0-9A-Fa-f]+$", value):
        return int(value, 16)
    _need(isinstance(value, int) and not isinstance(value, bool), where,
          f"not an integer: {value!r}")
    return value


def _ranges(raw, where):
    _need(isinstance(raw, dict) and raw, where, "ranges must be a non-empty object")
    out = {}
    for name, pair in raw.items():
        _need(isinstance(pair, list) and len(pair) == 2, f"{where}.{name}",
              "range must be [lo, hi]")
        lo, hi = (_int(v, f"{where}.{name}") for v in pair)
        _need(0 <= lo <= hi <= 255, f"{where}.{name}", "range must fit one byte, lo <= hi")
        out[name] = (lo, hi)
    return out


def _frame(template, name, ranges, where):
    _need(isinstance(template, str) and template.split(), where, "empty frame template")
    out, params = [], set()
    for tok in template.split():
        m = PARAM_RE.match(tok)
        if m:
            _need(m.group(1) in ranges, where, f"placeholder {tok} has no range")
            params.add(m.group(1))
            out.append(m.group(1))
        else:
            _need(BYTE_RE.match(tok), where, f"bad token {tok!r} (want 2 hex digits or {{name}})")
            out.append(int(tok, 16))
    _need(params == FRAME_PARAMS[name], where,
          f"needs placeholders {sorted(FRAME_PARAMS[name])}, has {sorted(params)}")
    return tuple(out)


def validate(raw, stem):
    """Return the normalised preset dict, or raise PresetError."""
    w = f"{stem}.json"
    _need(isinstance(raw, dict), w, "top level must be an object")
    missing = KEYS - OPTIONAL - set(raw)
    _need(not missing, w, f"missing keys: {sorted(missing)}")
    _need(not set(raw) - KEYS, w, f"unknown keys: {sorted(set(raw) - KEYS)}")
    _need(raw["id"] == stem and SLUG_RE.match(stem), w, "id must equal the file name (a slug)")
    _need(isinstance(raw["name"], str) and raw["name"].strip(), w, "name must be a string")
    match = raw["match"]
    _need(isinstance(match, dict) and set(match) == {"service_uuids", "name_hints"}, w,
          "match needs exactly service_uuids and name_hints")
    hints = match["name_hints"]
    _need(isinstance(hints, list) and all(isinstance(h, str) and h for h in hints), w,
          "name_hints must be a list of non-empty strings")
    gatt = raw["gatt"]
    _need(isinstance(gatt, dict) and set(gatt) == {"write", "notify"}, w,
          "gatt needs exactly write and notify")
    ranges = _ranges(raw["ranges"], f"{w}: ranges")
    frames = raw["frames"]
    _need(isinstance(frames, dict) and set(frames) == set(FRAME_PARAMS), w,
          f"frames must be exactly {sorted(FRAME_PARAMS)}")
    effects = raw["effects"]
    _need(isinstance(effects, dict) and effects, w, "effects must be a non-empty object")
    lo, hi = ranges.get("effect", (0, 255))
    ids = {}
    for name, value in effects.items():
        _need(SLUG_RE.match(name), w, f"effect name {name!r} is not a slug")
        ids[name] = _int(value, f"{w}: effects.{name}")
        _need(lo <= ids[name] <= hi, w, f"effect {name} id {ids[name]} outside {lo}..{hi}")
    _need(len(set(ids.values())) == len(ids), w, "duplicate effect ids")
    _need(raw["default_effect"] in ids, w, "default_effect is not in effects")
    return {
        "id": stem,
        "name": raw["name"].strip(),
        "service_uuids": tuple(_uuid(u, f"{w}: match") for u in match["service_uuids"]),
        "name_hints": tuple(hints),
        "write_uuid": _uuid(gatt["write"], f"{w}: gatt.write"),
        "notify_uuid": _uuid(gatt["notify"], f"{w}: gatt.notify"),
        "ranges": ranges,
        "frames": {k: _frame(frames[k], k, ranges, f"{w}: frames.{k}") for k in FRAME_PARAMS},
        "default_effect": raw["default_effect"],
        "effects": ids,
    }


def load_all(presets_dir):
    files = sorted(Path(presets_dir).glob("*.json"))
    if not files:
        raise PresetError(f"{presets_dir}: no presets found")
    out = {}
    for path in files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise PresetError(f"{path.name}: invalid JSON: {e}") from None
        out[path.stem] = validate(raw, path.stem)
    return out


def render(presets):
    """Deterministic source text: one line per preset field keeps it compact."""
    lines = ["PRESETS = {"]
    for pid, preset in presets.items():
        lines.append(f"    {pid!r}: {{")
        lines += [f"        {key!r}: {value!r}," for key, value in preset.items()]
        lines.append("    },")
    return HEADER + "\n".join(lines) + "\n}\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if the output is stale")
    ap.add_argument("--presets-dir", default=str(PRESETS_DIR))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)
    try:
        text = render(load_all(args.presets_dir))
    except PresetError as e:
        print(f"invalid preset: {e}", file=sys.stderr)
        return 2
    out = Path(args.out)
    current = out.read_text(encoding="utf-8") if out.exists() else None
    if args.check:
        if current != text:
            print(f"{out} is stale; run: python scripts/gen_presets.py", file=sys.stderr)
            return 1
        print(f"{out.name} is up to date")
        return 0
    if current != text:
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
