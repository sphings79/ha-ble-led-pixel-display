"""The BLE LED Pixel Display integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .api import BleLedPixelAPI, BleLedPixelConnectionError, BleLedPixelTimeoutError
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .services import async_setup_services

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
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BLE LED Pixel Display from a config entry."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    _LOGGER.debug("Setting up BLE LED Pixel Display for %s (%s)", name, address)
    
    # Create API instance with hass for Bluetooth proxy support
    api = BleLedPixelAPI(hass, address, entry=entry)
    
    # Test connection
    try:
        if not await api.connect():
            raise ConfigEntryNotReady(f"Failed to connect to LED panel at {address}")
        
        _LOGGER.info("Successfully connected to LED panel %s", address)
        
        # Get device info for sensors
        await api.get_device_info()
        
    except BleLedPixelTimeoutError as err:
        _LOGGER.error("Connection timeout to LED panel %s: %s", address, err)
        raise ConfigEntryNotReady(f"Connection timeout: {err}") from err
        
    except BleLedPixelConnectionError as err:
        _LOGGER.error("Failed to connect to LED panel %s: %s", address, err)
        raise ConfigEntryNotReady(f"Connection failed: {err}") from err
    
    # Store API instance in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api
    entry.runtime_data = api

    # Reload the entry whenever options change (e.g. dimension overrides)
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
        try:
            await api.disconnect()
            _LOGGER.debug("Disconnected from LED panel")
        except Exception as err:
            _LOGGER.error("Error disconnecting from device: %s", err)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)