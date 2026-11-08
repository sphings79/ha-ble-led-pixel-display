"""Brand names for newly seen panels, fetched from the project repository.

The table in advertisement.py ships with each release. A panel that is newer
than the installed release would stay "unknown" until the next one, so a small
JSON file in the repository (brands.json) is fetched as well and fills the
gaps. The built-in table always wins; this only adds to it.

The brand is cosmetic -- geometry comes from the device type -- so every
failure here is quiet: no network, a broken file or a refused request just
leaves the integration with what it already has.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING, Any

# Home Assistant is imported inside the functions that need it: advertisement.py
# imports this module, and it is plain Python that must stay importable alone.
if TYPE_CHECKING:
    import aiohttp
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

BRANDS_URL = (
    "https://raw.githubusercontent.com/sphings79/ha-ble-led-pixel-display/main/brands.json"
)
SCHEMA_VERSION = 1

# Brand data is tiny; anything bigger is not what we asked for.
MAX_RESPONSE_BYTES = 64 * 1024
REQUEST_TIMEOUT = 10

# How often the table is fetched again while Home Assistant runs.
REFRESH_INTERVAL_HOURS = 24

STORE_KEY = "ble_led_pixel_brands"
STORE_VERSION = 1

_CIDPID = re.compile(r"^\d{6}$")
_MAX_BRAND_LENGTH = 40

# Entries from the fetched file (or its cache). Replaced as a whole, never
# edited in place, so a reader never sees a half-updated table.
_remote: dict[str, str] = {}


def remote_brand(cidpid: str) -> str | None:
    """Brand from the fetched table, or None."""
    return _remote.get(cidpid)


def set_remote(brands: dict[str, str]) -> bool:
    """Replace the fetched table. Returns True when it changed."""
    global _remote
    if brands == _remote:
        return False
    _remote = dict(brands)
    return True


def parse_brands(data: Any) -> dict[str, str] | None:
    """Validate a decoded brands file.

    Returns the usable entries, or None when the document as a whole is not
    acceptable (wrong shape or an unknown schema version). Single bad entries
    are dropped rather than failing the lot: the brand ends up in the device
    registry, so only a plain, short, printable name is taken.
    """
    if not isinstance(data, dict) or data.get("schema") != SCHEMA_VERSION:
        return None
    entries = data.get("brands")
    if not isinstance(entries, dict):
        return None

    brands: dict[str, str] = {}
    for cidpid, name in entries.items():
        if not isinstance(cidpid, str) or not _CIDPID.match(cidpid):
            continue
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name or len(name) > _MAX_BRAND_LENGTH or not name.isprintable():
            continue
        brands[cidpid] = name
    return brands


async def async_fetch(session: aiohttp.ClientSession) -> dict[str, str] | None:
    """Download and validate the brands file. None on any failure."""
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with session.get(BRANDS_URL) as response:
                if response.status != 200:
                    _LOGGER.debug("Brand table request answered %s", response.status)
                    return None
                body = await response.content.read(MAX_RESPONSE_BYTES + 1)
    except Exception as err:  # noqa: BLE001 - aiohttp, timeout or socket: all the same here
        _LOGGER.debug("Could not fetch the brand table: %s", err)
        return None

    if len(body) > MAX_RESPONSE_BYTES:
        _LOGGER.debug("Brand table is larger than %d bytes, ignored", MAX_RESPONSE_BYTES)
        return None
    try:
        data = json.loads(body)
    except ValueError:
        _LOGGER.debug("Brand table is not valid JSON, ignored")
        return None

    brands = parse_brands(data)
    if brands is None:
        _LOGGER.debug("Brand table has an unexpected layout, ignored")
    return brands


async def async_load_cache(hass: HomeAssistant) -> bool:
    """Load the last good table from storage. Returns True when it changed."""
    from homeassistant.helpers.storage import Store

    try:
        stored = await Store(hass, STORE_VERSION, STORE_KEY).async_load()
    except Exception as err:  # noqa: BLE001 - a broken cache must not stop setup
        _LOGGER.debug("Could not read the brand table cache: %s", err)
        return False
    # Validated again: the file could have been edited by hand.
    brands = parse_brands(stored)
    return set_remote(brands) if brands is not None else False


async def async_refresh(hass: HomeAssistant) -> bool:
    """Fetch the table, keep it and store it. Returns True when it changed."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.helpers.storage import Store

    brands = await async_fetch(async_get_clientsession(hass))
    if brands is None:
        return False
    changed = set_remote(brands)
    if changed:
        try:
            await Store(hass, STORE_VERSION, STORE_KEY).async_save(
                {"schema": SCHEMA_VERSION, "brands": brands}
            )
        except Exception as err:  # noqa: BLE001 - the table works without a cache
            _LOGGER.debug("Could not store the brand table: %s", err)
        _LOGGER.debug("Brand table updated: %d entries", len(brands))
    return changed
