"""Storage as JSON files in one directory, written atomically (any OS)."""
import json
import os

ADDRESS_ENV = "DESKGLOW_ADDRESS"


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


class JsonFileStorage:
    """config.json and state.json in `directory`; the daemon log at `log_file`."""

    def __init__(self, directory, log_file=None, env=None):
        self._env = os.environ if env is None else env
        self._dir = directory
        self._log = log_file or os.path.join(directory, "daemon.log")
        self.config_file = os.path.join(self._dir, "config.json")
        self.state_file = os.path.join(self._dir, "state.json")

    def config_dir(self):
        return self._dir

    def log_path(self):
        return self._log

    def address_override(self):
        return self._env.get(ADDRESS_ENV) or None

    def _write(self, path, obj):
        os.makedirs(self._dir, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
        os.replace(tmp, path)

    def load_config(self):
        cfg = _read_json(self.config_file)
        return cfg if isinstance(cfg, dict) else {}

    def save_config(self, cfg):
        self._write(self.config_file, cfg)

    def load_state(self):
        state = _read_json(self.state_file)
        return state if isinstance(state, dict) else None

    def save_state(self, state):
        self._write(self.state_file, state)
