"""BlueZ housekeeping: drop stale bonds (D-Bus, else bluetoothctl) and reset
the adapter (bluetoothctl)."""
import logging
import subprocess
import time

from ..services.link import AdapterError
from . import bluez_dbus

RESET_PAUSE = 3.0   # seconds between adapter power off / on / bond removal
log = logging.getLogger("deskglow.bluez")


def _remove_with_bluetoothctl(address):
    subprocess.run(["bluetoothctl", "remove", address], capture_output=True, timeout=10)


def drop_bond(address, dbus_remove=None):
    """Remove a stale bond that makes BlueZ hang on ServicesResolved. Never raises.

    Asks BlueZ directly over D-Bus (Adapter1.RemoveDevice); if the bus is
    unreachable or refuses, falls back to `bluetoothctl remove`."""
    try:
        (dbus_remove or bluez_dbus.remove_device)(address)
        return
    except Exception as e:
        log.debug("D-Bus RemoveDevice failed (%s); trying bluetoothctl", e)
    try:
        _remove_with_bluetoothctl(address)
    except Exception:
        pass


def _bt(*args):
    subprocess.run(["bluetoothctl", *args], capture_output=True, timeout=12)


def reset_adapter(address=None, sleep=time.sleep):
    """Power-cycle the adapter, then forget `address`'s bond/cache (if given)."""
    try:
        _bt("power", "off")
        sleep(RESET_PAUSE)
        _bt("power", "on")
        sleep(RESET_PAUSE)
    except FileNotFoundError:
        raise AdapterError("'bluetoothctl' was not found. Install BlueZ "
                           "(e.g. sudo apt install bluez) and try again.") from None
    except subprocess.SubprocessError as e:
        raise AdapterError(f"bluetoothctl failed: {e}") from e
    if address:
        drop_bond(address)   # clear any stale bond/cache
