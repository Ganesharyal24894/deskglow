"""The configured strip address and the persisted daemon state, on top of Storage."""
from ..model.settings import state_from
from .discovery import UNKNOWN_NAME


class SettingsStore:
    """Policy over raw Storage: where the address comes from and how a saved
    state is completed with defaults."""

    def __init__(self, storage):
        self.storage = storage

    def get_address(self):
        """The strip's MAC. The environment override wins, then the saved
        config. None if unset (the CLI then prompts `setup` to discover it)."""
        return self.storage.address_override() or self.storage.load_config().get("address")

    def get_device_name(self):
        """The advertised name of the configured strip, if setup saw one."""
        return self.storage.load_config().get("name")

    def set_address(self, addr, name=None):
        """Save the strip's address with its advertised name (some platforms
        find the strip again by name when the saved address goes stale); a
        missing name clears any name saved for a previous strip."""
        cfg = self.storage.load_config()
        cfg["address"] = addr
        if name and name != UNKNOWN_NAME:
            cfg["name"] = name
        else:
            cfg.pop("name", None)
        self.storage.save_config(cfg)

    def forget(self):
        """Clear the configured strip (the environment override still wins)."""
        cfg = self.storage.load_config()
        cfg.pop("address", None)
        cfg.pop("name", None)
        self.storage.save_config(cfg)

    def load_state(self):
        return state_from(self.storage.load_state())

    def save_state(self, state):
        self.storage.save_state(state)
