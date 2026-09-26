"""Safety nets for driver tests: no test may reach a real system/session bus
(a real BlueZ RemoveDevice would forget a device on the developer's machine)."""
import pytest

from deskglow.drivers import bluez_dbus


@pytest.fixture(autouse=True)
def no_real_system_bus(monkeypatch):
    async def refuse(_dbus):
        raise RuntimeError("tests must not connect to the real D-Bus system bus")
    monkeypatch.setattr(bluez_dbus, "_system_bus", refuse)
