"""Persistent config (the strip address) and daemon state (mode, settings)."""
from typing import Protocol


class Storage(Protocol):
    def load_config(self) -> dict:
        """The saved config, or {} if missing or unreadable."""

    def save_config(self, cfg: dict) -> None:
        """Replace the config atomically (never a half-written file)."""

    def load_state(self) -> dict | None:
        """The saved daemon state as stored, or None if missing or unreadable."""

    def save_state(self, state: dict) -> None:
        """Replace the state atomically."""

    def address_override(self) -> str | None:
        """A strip address forced by the environment (DESKGLOW_ADDRESS), if any."""

    def config_dir(self) -> str: ...

    def log_path(self) -> str:
        """Where a daemon started by a client writes its log."""
