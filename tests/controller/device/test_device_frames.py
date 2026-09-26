"""The frames Device puts on the wire, pinned as literal bytes as well."""
from device_harness import connected_device
from fakes import ENCODER

ON = bytes.fromhex("7E 00 04 F0 00 01 FF 00 EF")
OFF = bytes.fromhex("7E 00 04 00 00 00 FF 00 EF")
FULL = bytes.fromhex("7E 00 01 64 00 00 00 00 EF")
WHITE = bytes.fromhex("7E 00 05 03 FF FF FF 00 EF")


async def test_power_emits_the_expected_frames(ble):
    """The ELK-BLEDOM on/off frames, unacknowledged unless asked otherwise."""
    dev = await connected_device(ble)
    mark = ble.mark()
    await dev.power(True)
    await dev.power(False)
    await dev.power(True, reliable=True)
    assert ble.frames_since(mark) == [ON, OFF, ON]
    assert ble.frames_since(mark) == [
        ENCODER.power(True), ENCODER.power(False), ENCODER.power(True)]
    assert ble.responses_since(mark) == [False, False, True]


async def test_send_frame_writes_the_frame_verbatim(ble):
    """send_frame is the raw escape hatch: no rewriting, no de-duplication."""
    dev = await connected_device(ble)
    mark = ble.mark()
    await dev.send_frame(ENCODER.effect(0x87))
    await dev.send_frame(ENCODER.effect(0x87))
    await dev.send_frame(ENCODER.speed(50), reliable=True)
    assert ble.frames_since(mark) == [
        bytes.fromhex("7E 00 03 87 03 00 00 00 EF"),
        bytes.fromhex("7E 00 03 87 03 00 00 00 EF"),
        bytes.fromhex("7E 00 02 32 00 00 00 00 EF")]
    assert ble.responses_since(mark) == [False, False, True]


async def test_set_rgb_emits_a_colour_frame_and_clamps_via_the_encoder(ble):
    """set_rgb's payload is exactly the encoder's colour frame."""
    dev = await connected_device(ble)
    mark = ble.mark()
    await dev.set_rgb(300, -5, 12.7)
    assert ble.frames_since(mark) == [ENCODER.color(255, 0, 12)]
    assert ble.frames_since(mark) == [bytes.fromhex("7E 00 05 03 FF 00 0C 00 EF")]


async def test_reset_known_good_uses_acknowledged_writes(ble):
    """Breaking the strip out of a button-pressed effect mode needs writes that
    are actually confirmed, otherwise they are silently dropped."""
    dev = await connected_device(ble)
    mark = ble.mark()
    await dev.reset_known_good()
    assert ble.frames_since(mark) == [ON, FULL, WHITE, WHITE]
    assert ble.responses_since(mark) == [True, True, True, True]
