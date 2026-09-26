"""Starting, spawning and recycling the daemon process."""
from typing import Protocol


class Autostart(Protocol):
    def start(self) -> bool:
        """Start the installed login service (e.g. a systemd user unit) now.
        True if the service manager accepted the request."""

    def is_enabled(self) -> bool:
        """True if the daemon is set to start when the user logs in."""

    def set_enabled(self, enabled: bool) -> None:
        """Turn start-at-login on or off (install/remove the login entry).
        Raises OSError if the platform's service manager refuses."""


class ProcessControl(Protocol):
    def spawn_daemon(self) -> None:
        """Start a detached daemon process that logs to Storage.log_path()."""

    def try_begin_spawn(self) -> bool:
        """Claim the right to spawn a daemon (non-blocking). Only one caller in
        this process may hold it; True if claimed."""

    def end_spawn(self) -> None:
        """Release the claim taken by try_begin_spawn()."""

    def exit_for_restart(self, code: int = 1) -> None:
        """Exit immediately with `code` so the service manager restarts us
        with fresh resources. Does not return."""
