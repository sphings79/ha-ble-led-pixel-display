"""Extract the product identity from a panel's Bluetooth advertisement.

Panels carry a component id (cid) and product id (pid) in their manufacturer
data. Together they identify the model, which matters for two reasons: three
device types resolve to different hardware depending on the pid (see
device_types), and the pair maps to a brand.

The vendor app reads these from the raw scan record at fixed offsets, anchored
on the signature "TR\\0r":

    scanRecord[27..30] == {0x54, 0x52, 0x00, 0x72}
    cid = decimal(scanRecord[31]) + decimal(scanRecord[32]), left-padded to 4
    pid = decimal(scanRecord[33]),                left-padded to 2, or 3 if >= 100

Home Assistant hands integrations parsed manufacturer data rather than the raw
record, and strips the company id, so those offsets do not carry over directly.
This module therefore searches every manufacturer-data block for the signature
instead of trusting a fixed position, and falls back to the layout the app uses
for its non-LED_BLE branch. Anything it cannot parse is logged at debug level
with the raw bytes, so an unrecognised panel can be diagnosed from a log rather
than guessed at.

Source: com/wifiled/ipixels/core/BleManager$bleScanCallback$1.onLeScan().
"""
from __future__ import annotations

import logging
from typing import NamedTuple

_LOGGER = logging.getLogger(__name__)

# "TR\0r" -- marks the vendor's payload inside the advertisement.
SIGNATURE = bytes([0x54, 0x52, 0x00, 0x72])

# The app matches company id 0x5452 ("TR"). Home Assistant reports the same
# field byte-swapped, as 0x5254, because it reads the id little-endian per the
# BLE spec. Accept both rather than depend on which way round a given stack
# hands it over.
COMPANY_IDS = (0x5452, 0x5254)

# cidpid prefixes to brand, from http://app.heaton.cn/homeConfig.json
BRANDS: dict[str, str] = {
    **{f"0025{n:02d}": "HYPERLITE" for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14)},
    **{f"0025{n:02d}": "EZYEVY" for n in (10, 11, 12)},
}


class PanelIdentity(NamedTuple):
    """Product identity read from an advertisement."""

    cid: str | None
    pid: str | None
    around: int | None
    device_type: int | None = None

    @property
    def cidpid(self) -> str | None:
        """The combined identifier the vendor uses for a model."""
        if self.cid is None or self.pid is None:
            return None
        return f"{self.cid}{self.pid}"

    @property
    def brand(self) -> str | None:
        """Brand name, where the model is known to belong to one."""
        return BRANDS.get(self.cidpid) if self.cidpid else None


def _decode(payload: bytes, offset: int) -> PanelIdentity | None:
    """Decode cid, pid and the 'around' byte at a signature offset."""
    # cid and pid follow the four signature bytes.
    if len(payload) < offset + 7:
        return None
    b_cid_hi, b_cid_lo, b_pid = payload[offset + 4 : offset + 7]

    # The app builds these as decimal strings, not as hex or a plain integer:
    # two bytes rendered decimal and concatenated, then left-padded.
    cid = f"{b_cid_hi}{b_cid_lo}".rjust(4, "0")[-4:]
    width = 3 if b_pid >= 100 else 2
    pid = str(b_pid).rjust(width, "0")[-width:]

    around = payload[offset + 7] if len(payload) > offset + 7 else None
    return PanelIdentity(cid=cid, pid=pid, around=around)


def parse_identity(manufacturer_data: dict[int, bytes] | None) -> PanelIdentity:
    """Read the product identity from a Home Assistant advertisement.

    Args:
        manufacturer_data: As provided by BluetoothServiceInfo, keyed by
            company id, with the company id itself already stripped.

    Returns:
        A PanelIdentity. Fields are None when nothing could be parsed, so
        callers can carry on without the identity rather than get a guess.
    """
    if not manufacturer_data:
        return PanelIdentity(None, None, None, None)

    for company_id, payload in manufacturer_data.items():
        # Preferred: locate the signature rather than assume an offset, since
        # Home Assistant's framing differs from the raw scan record.
        index = payload.find(SIGNATURE)
        if index != -1:
            identity = _decode(payload, index)
            if identity is not None:
                _LOGGER.debug(
                    "Identity from company 0x%04X at offset %d: cid=%s pid=%s",
                    company_id, index, identity.cid, identity.pid,
                )
                return identity

        # Real panels put the signature in the company id and start the
        # payload one byte in, with 0x72 ('r') as the marker:
        #
        #   00 72 00 07 02 00 81
        #      \  \___/  \  \  \__ device type
        #       \    \    \  \____ around
        #        \    \    \______ pid
        #         \    \__________ cid, two bytes rendered decimal
        #          \______________ marker
        if company_id in COMPANY_IDS and len(payload) > 4 and payload[1] == 0x72:
            b_cid_hi, b_cid_lo, b_pid = payload[2], payload[3], payload[4]
            cid = f"{b_cid_hi}{b_cid_lo}".rjust(4, "0")[-4:]
            width = 3 if b_pid >= 100 else 2
            identity = PanelIdentity(
                cid=cid,
                pid=str(b_pid).rjust(width, "0")[-width:],
                around=payload[5] if len(payload) > 5 else None,
                device_type=payload[6] if len(payload) > 6 else None,
            )
            _LOGGER.debug("Identity from advertisement: cid=%s pid=%s device_type=%s",
                          identity.cid, identity.pid, identity.device_type)
            return identity

    _LOGGER.debug(
        "No product identity in advertisement. Raw manufacturer data: %s. "
        "Please report this along with your panel's model name.",
        {f"0x{cid:04X}": data.hex() for cid, data in manufacturer_data.items()},
    )
    return PanelIdentity(None, None, None, None)
