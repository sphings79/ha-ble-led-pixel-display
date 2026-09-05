"""The BLE LED Pixel Display integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .api import BleLedPixelAPI, BleLedPixelConnectionError, BleLedPixelTimeoutError
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .fonts import build_font_index
from .services import async_setup_services
from .unknown_panel import async_report_unknown_panel

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.TEXT, Platform.SENSOR, Platform.SELECT, Platform.NUMBER, Platform.BUTTON, Platform.LIGHT]




# Type alias for LED panel config entries


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the BLE LED Pixel Display integration (not tied to any config entry).

    Registers all ble_led_pixel.* actions here so they exist in Home
    Assistant's service registry immediately at startup - see
    https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup/
    """
    # Build the font index once, off the event loop. Every later lookup -
    # the font selector, text rendering, the send_text action - reads from
    # that cache instead of scanning the filesystem.
    await hass.async_add_executor_job(build_font_index)

    async_setup_services(hass)
    return True


# Entities this integration used to create. Left behind in the registry they
# would sit there as permanently unavailable, so they are removed on setup.
# (unique_id suffix, platform)
REMOVED_ENTITIES: tuple[tuple[str, str], ...] = (
    # Replaced in 2.0.0 by select.<panel>_text_effect, which names the effects
    # instead of numbering them.
    ("text_animation", Platform.NUMBER),
)


@callback
def _remove_retired_entities(hass: HomeAssistant, address: str) -> None:
    """Drop registry entries for entities this version no longer creates."""
    registry = er.async_get(hass)
    for suffix, platform in REMOVED_ENTITIES:
        entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{address}_{suffix}")
        if entity_id is None:
            continue
        registry.async_remove(entity_id)
        _LOGGER.info("Removed %s, which this version no longer provides", entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BLE LED Pixel Display from a config entry."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    _LOGGER.debug("Setting up BLE LED Pixel Display for %s (%s)", name, address)
    
    _remove_retired_entities(hass, address)

    # Create API instance with hass for Bluetooth proxy support
    api = BleLedPixelAPI(hass, address, entry=entry)

    # Start this before connecting. A panel stops advertising once it is
    # connected, so the product identity is only on air while the link is
    # down -- catching it here is what makes it survive the connect.
    api.start_identity_watch()
    
    # Try to connect, but do not fail the setup when the panel is not reachable
    # right now. A battery-less BLE panel comes and goes: at startup Home
    # Assistant's Bluetooth manager often has no fresh advertisement cached yet,
    # and aborting here left the entry unloaded with nothing scheduling a retry
    # once the panel reappeared. The watcher started below handles that, so the
    # entities exist immediately and turn available as soon as the link is up.
    try:
        if await api.connect():
            _LOGGER.info("Successfully connected to LED panel %s", address)
            await api.get_device_info()
        else:
            _LOGGER.warning(
                "LED panel %s not reachable yet; the reconnect watcher will "
                "connect as soon as it advertises", address,
            )
    except (BleLedPixelTimeoutError, BleLedPixelConnectionError) as err:
        _LOGGER.warning(
            "LED panel %s not reachable yet (%s); the reconnect watcher will "
            "connect as soon as it advertises", address, err,
        )
    
    # Store API instance in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api
    entry.runtime_data = api

    # An unrecognised panel gets a repair notice with a prefilled bug report.
    # Everything technical is already known at this point; only the name on the
    # box is not, and that is what the notice asks for.
    await async_report_unknown_panel(hass, address, api.device_info)

    # Watch for the panel dropping its link and bring it back automatically.
    # Without this a lost connection stays lost until someone reloads the
    # config entry by hand - which is what happens after a restart when the
    # panel was not in Home Assistant's Bluetooth cache at setup time.
    await api.start_watcher()

    # Reload the entry whenever options change (e.g. dimension overrides).
    # Remember what it was set up with, because the listener fires on any
    # change to the entry -- including the identity the advertisement watcher
    # writes into entry.data, which must not restart the integration.
    api.setup_options = dict(entry.options)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading BLE LED Pixel Display integration")
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Disconnect from device
        api: BleLedPixelAPI = hass.data[DOMAIN].pop(entry.entry_id)
        api.stop_identity_watch()
        await api.stop_watcher()
        try:
            await api.disconnect()
            _LOGGER.debug("Disconnected from LED panel")
        except Exception as err:
            _LOGGER.error("Error disconnecting from device: %s", err)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry, but only when its options actually changed."""
    api = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if api is not None and getattr(api, "setup_options", None) == dict(entry.options):
        _LOGGER.debug("Entry data changed without an options change; not reloading")
        return

    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)