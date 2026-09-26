"""Typed access to the generated controller presets (see presets/controllers/)."""
from dataclasses import dataclass

from .presets_gen import PRESETS

DEFAULT_PRESET_ID = "elk-bledom"

FrameTemplate = tuple[int | str, ...]


@dataclass(frozen=True)
class Preset:
    """Everything controller-specific: how to recognise it, where to write,
    how each command is framed, and its built-in effect table."""

    id: str
    name: str
    service_uuids: tuple[str, ...]
    name_hints: tuple[str, ...]
    write_uuid: str
    notify_uuid: str
    ranges: dict[str, tuple[int, int]]
    frames: dict[str, FrameTemplate]
    default_effect: str
    effects: dict[str, int]

    def effect_names(self):
        """Effect names in table order (the order the CLI lists them)."""
        return list(self.effects)


def preset_ids():
    return list(PRESETS)


def get_preset(preset_id=None):
    """The preset with this id (default: the ELK-BLEDOM family), or KeyError."""
    pid = preset_id or DEFAULT_PRESET_ID
    if pid not in PRESETS:
        raise KeyError(f"unknown controller preset {pid!r}; known: {', '.join(PRESETS)}")
    # copy the tables so no caller can mutate the shared generated data
    return Preset(**{k: dict(v) if isinstance(v, dict) else v for k, v in PRESETS[pid].items()})
