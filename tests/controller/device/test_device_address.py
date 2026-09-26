"""Device.address: explicit override, else the injected address source."""
import pytest

from deskglow.controller import device
from device_harness import ADDR, OTHER_ADDR, make_device
from fakes import ENCODER


def test_explicit_constructor_address_wins_over_the_address_source(ble):
    """An address passed to Device() overrides the configured one."""
    dev = make_device(ble, address=ADDR, address_source=lambda: OTHER_ADDR)
    assert dev.address == ADDR


def test_address_falls_back_to_the_address_source(ble):
    """With no explicit address, the configured address (env or config) is used."""
    dev = make_device(ble, address=None, address_source=lambda: OTHER_ADDR)
    assert dev.address == OTHER_ADDR


def test_address_is_none_when_nothing_is_configured(ble):
    """A fresh install has no strip address at all."""
    assert make_device(ble, address=None).address is None
    assert device.Device(ble, ENCODER).address is None


def test_address_is_reread_each_time_so_setup_takes_effect_immediately(ble):
    """`deskglow setup` writes the config; a running daemon must pick it up."""
    box = {"addr": None}
    dev = make_device(ble, address=None, address_source=lambda: box["addr"])
    assert dev.address is None
    box["addr"] = ADDR
    assert dev.address == ADDR


async def test_writing_without_a_configured_address_points_at_deskglow_setup(ble):
    """The unconfigured case must be a clear ConnectionError, not a stray crash."""
    dev = make_device(ble, address=None)
    with pytest.raises(ConnectionError) as exc:
        await dev.power(True)
    assert "deskglow setup" in str(exc.value)
    assert ble.clients == [], "must not touch the radio with no address configured"
    assert ble.scans == 0
