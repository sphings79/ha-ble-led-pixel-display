"""Product identity from advertisements."""
from custom_components.ble_led_pixel.advertisement import (
    SIGNATURE,
    parse_identity,
)


def test_real_panel_layout():
    # Company id 0x5254 carries the marker at payload[1]: cid 00 07, pid 2.
    identity = parse_identity({0x5254: bytes([0x00, 0x72, 0, 7, 2, 0, 0x81])})
    assert identity.cid == "0007"
    assert identity.pid == "02"
    assert identity.device_type == 0x81
    assert identity.brand == "B.K. Light"


def test_signature_anywhere_in_payload():
    payload = b"\xaa\xbb" + SIGNATURE + bytes([0, 25, 3, 9])
    identity = parse_identity({0x1234: payload})
    assert (identity.cid, identity.pid, identity.around) == ("0025", "03", 9)
    assert identity.brand == "HYPERLITE"


def test_three_digit_pid():
    identity = parse_identity({0x5254: bytes([0x00, 0x72, 0, 1, 130])})
    assert identity.pid == "130"


def test_nothing_parseable():
    for data in (None, {}, {0x1111: b"\x01\x02"}):
        identity = parse_identity(data)
        assert identity.cid is None and identity.cidpid is None
        assert identity.brand is None
