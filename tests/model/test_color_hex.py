"""deskglow.model.color: hex conversion used by status replies and the app."""
import pytest

from deskglow.model.color import from_hex, to_hex


def test_to_hex_is_uppercase_and_clamped():
    assert to_hex((255, 180, 110)) == "#FFB46E"
    assert to_hex((300, -5, 9.6)) == "#FF000A"


@pytest.mark.parametrize("text", ["#ffb46e", "FFB46E", " #FfB46e "])
def test_from_hex_accepts_either_case_with_or_without_hash(text):
    assert from_hex(text) == (255, 180, 110)


@pytest.mark.parametrize("text", ["#FFB46", "#GGGGGG", "", "#FFB46E0"])
def test_from_hex_rejects_garbage(text):
    with pytest.raises(ValueError):
        from_hex(text)
