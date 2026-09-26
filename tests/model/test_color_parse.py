"""deskglow.model.color: parsing colours from CLI tokens.

Pure functions only: no device, no I/O, no timing.
"""
import pytest

from deskglow.model import color


# --------------------------------------------------------------- parse() ----

@pytest.mark.parametrize("name,expected", sorted(color.NAMED.items()))
def test_parse_every_named_colour(name, expected):
    """Every entry in NAMED is reachable by its own name."""
    assert color.parse([name]) == expected


@pytest.mark.parametrize("token", ["RED", "Red", "rEd"])
def test_parse_named_colour_is_case_insensitive(token):
    """Colour names are matched case-insensitively."""
    assert color.parse([token]) == (255, 0, 0)


@pytest.mark.parametrize("token,expected", [
    ("#ff8800", (255, 136, 0)),
    ("#FF8800", (255, 136, 0)),      # uppercase hex
    ("ff8800", (255, 136, 0)),       # bare, because zsh eats a leading '#'
    ("FF8800", (255, 136, 0)),
    ("#000000", (0, 0, 0)),
    ("#ffffff", (255, 255, 255)),
    ("#010203", (1, 2, 3)),
    ("00ff00", (0, 255, 0)),
])
def test_parse_six_digit_hex(token, expected):
    """'#rrggbb' and bare 'rrggbb' both decode, in either case."""
    assert color.parse([token]) == expected


@pytest.mark.parametrize("tokens,expected", [
    (["0", "0", "0"], (0, 0, 0)),
    (["255", "255", "255"], (255, 255, 255)),
    (["12", "34", "56"], (12, 34, 56)),
])
def test_parse_three_decimal_tokens(tokens, expected):
    """Three plain decimal tokens are an r/g/b triple."""
    assert color.parse(tokens) == expected


@pytest.mark.parametrize("tokens,expected", [
    (["0x10", "0x20", "0x30"], (16, 32, 48)),
    (["0xFF", "0", "0"], (255, 0, 0)),
    (["0b1010", "0o17", "10"], (10, 15, 10)),
])
def test_parse_three_prefixed_tokens(tokens, expected):
    """Python integer literal prefixes (0x/0o/0b) are accepted per channel."""
    assert color.parse(tokens) == expected


@pytest.mark.parametrize("tokens,expected", [
    (["300", "10", "20"], (255, 10, 20)),      # above 255 clamps down
    (["-5", "10", "20"], (0, 10, 20)),         # below 0 clamps up
    (["999", "-999", "128"], (255, 0, 128)),
])
def test_parse_clamps_out_of_range_channels(tokens, expected):
    """Numeric triples are clamped into 0..255 rather than rejected."""
    assert color.parse(tokens) == expected


def test_parse_accepts_zero_padded_decimal_tokens():
    """`deskglow color 08 10 20` should mean (8, 16, 32)-style decimals, not an error.

    Note the intent: with int(x, 0) semantics '10' and '20' are decimal, so the
    only thing at stake is that a leading zero must not be fatal.
    """
    assert color.parse(["08", "10", "20"]) == (8, 10, 20)


@pytest.mark.parametrize("tokens", [
    ["nosuchcolour"],
    ["#ff88"],            # too short
    ["#ff88000"],         # too long
    ["#gggggg"],          # not hex digits
    ["ff88zz"],
    [""],
])
def test_parse_rejects_bad_single_token(tokens):
    """A single unrecognised token is a ValueError, not a silent black."""
    with pytest.raises(ValueError):
        color.parse(tokens)


@pytest.mark.parametrize("tokens", [[], ["1", "2"], ["1", "2", "3", "4"]])
def test_parse_rejects_wrong_token_count(tokens):
    """Only 1 or 3 tokens make a colour."""
    with pytest.raises(ValueError):
        color.parse(tokens)


@pytest.mark.parametrize("tokens", [["a", "b", "c"], ["1.5", "2", "3"]])
def test_parse_rejects_non_integer_triples(tokens):
    """Non-integer channel tokens are a ValueError."""
    with pytest.raises(ValueError):
        color.parse(tokens)
