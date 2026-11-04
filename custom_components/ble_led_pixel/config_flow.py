"""Config flow for BLE LED Pixel Display integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import BleLedPixelAPI, BleLedPixelConnectionError, BleLedPixelTimeoutError
from .advertisement import PanelIdentity, parse_identity
from .bluetooth.scanner import discover_panels
from .const import (
    DOMAIN,
    CONF_ADDRESS,
    OPT_OVERRIDE_DIMENSIONS,
    OPT_PANEL_WIDTH,
    OPT_PANEL_HEIGHT,
    OPT_FORCE_FEATURES,
    OPT_PASSWORD,
)

_LOGGER = logging.getLogger(__name__)

CHOICE_MANUAL = "manual"
CHOICE_ALL = "all"


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAddress(HomeAssistantError):
    """Error to indicate there is invalid address."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    address = data[CONF_ADDRESS]

    # Create API instance with hass for Bluetooth proxy support
    api = BleLedPixelAPI(hass, address)
    
    try:
        # Test connection
        if not await api.connect():
            raise CannotConnect
        
        # Disconnect after successful test
        await api.disconnect()
        
    except BleLedPixelTimeoutError as err:
        raise CannotConnect from err
    except BleLedPixelConnectionError as err:
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.exception("Unexpected exception")
        raise CannotConnect from err

    # Return info that you want to store in the config entry.
    return {"title": f"LED panel {address[-8:]}", "address": address}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BLE LED Pixel Display."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self._discovered_devices: dict[str, dict[str, Any]] = {}
        self._identity = PanelIdentity(None, None, None, None)

    def _identity_data(self) -> dict[str, Any]:
        """Entry data for the identity, empty when nothing could be read."""
        if self._identity.cid is None:
            return {}
        return {
            "cid": self._identity.cid,
            "pid": self._identity.pid,
            "around": self._identity.around,
            "adv_device_type": self._identity.device_type,
        }

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlowHandler":
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return await self._show_discovery_form()

        return await self._handle_device_selection(user_input)

    def _scan(self) -> dict[str, str]:
        """Refresh the discovered devices; return form errors."""
        try:
            discovered = discover_panels(self.hass, return_all=True)
        except Exception:  # noqa: BLE001 - discovery must never break the flow
            _LOGGER.exception("CONFIG_FLOW: Discovery failed")
            self._discovered_devices = {}
            return {"base": "discovery_failed"}
        configured = self._async_current_ids(include_ignore=False)
        self._discovered_devices = {
            device["address"]: device
            for device in discovered
            if device["address"] not in configured
        }
        _LOGGER.debug(
            "CONFIG_FLOW: %d unconfigured devices (%d panels)",
            len(self._discovered_devices),
            sum(1 for d in self._discovered_devices.values() if d.get("is_compatible")),
        )
        return {}

    def _device_options(self, panels_only: bool) -> dict[str, str]:
        """Selector options: panels first, then (optionally) everything else."""
        devices = sorted(
            self._discovered_devices.items(),
            key=lambda item: (not item[1].get("is_compatible", False), item[1]["name"]),
        )
        options: dict[str, str] = {}
        for address, device in devices:
            compatible = device.get("is_compatible", False)
            if panels_only and not compatible:
                continue
            label = f"{device['name']} ({address})"
            options[address] = f"⭐ {label}" if compatible and not panels_only else label
        if panels_only:
            others = sum(
                1 for d in self._discovered_devices.values() if not d.get("is_compatible")
            )
            if others:
                options[CHOICE_ALL] = f"Show all Bluetooth devices ({others} more)"
        options[CHOICE_MANUAL] = "Manual entry"
        return options

    async def _show_discovery_form(
        self, connect_errors: dict[str, str] | None = None
    ) -> FlowResult:
        """List the panels found nearby that are not set up yet."""
        errors = self._scan() or dict(connect_errors or {})
        if not errors and not any(
            d.get("is_compatible") for d in self._discovered_devices.values()
        ):
            errors["base"] = "no_devices_found"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(self._device_options(panels_only=True))}
            ),
            errors=errors,
            description_placeholders={
                "device_count": str(len(self._discovered_devices))
            },
        )

    async def async_step_pick_any(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Pick from every connectable Bluetooth device, panels starred.

        For a panel that advertises under another name and without the
        vendor's manufacturer data, so it does not show up as a panel.
        """
        if user_input is not None:
            return await self._handle_device_selection(user_input, step_id="pick_any")
        return self._pick_any_form({})

    def _pick_any_form(self, errors: dict[str, str]) -> FlowResult:
        return self.async_show_form(
            step_id="pick_any",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(self._device_options(panels_only=False))}
            ),
            errors=errors,
        )

    async def _handle_device_selection(
        self, user_input: dict[str, Any], step_id: str = "user"
    ) -> FlowResult:
        """Handle device selection from discovery."""
        selected = user_input["device"]

        if selected == CHOICE_MANUAL:
            return await self.async_step_manual()
        if selected == CHOICE_ALL:
            return await self.async_step_pick_any()
        
        # Use discovered device
        device_info = self._discovered_devices.get(selected)
        if not device_info:
            return self.async_abort(reason="device_not_found")
        
        # Validate connection
        errors = {}
        try:
            info = await validate_input(
                self.hass, 
                {
                    CONF_ADDRESS: device_info["address"],
                    CONF_NAME: device_info["name"]
                }
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAddress:
            errors["base"] = "invalid_address"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        
        if errors:
            if step_id == "pick_any":
                return self._pick_any_form(errors)
            return await self._show_discovery_form(errors)

        # Check if already configured
        await self.async_set_unique_id(device_info["address"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=info["title"],
            data={
                CONF_ADDRESS: device_info["address"],
                CONF_NAME: device_info["name"],
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual device entry."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME, default="LED panel Display"): str,
                }),
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAddress:
            errors["base"] = "invalid_address"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Check if already configured
            await self.async_set_unique_id(user_input[CONF_ADDRESS])
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=info["title"], 
                data=user_input
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS, default=user_input.get(CONF_ADDRESS, "")): str,
                vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME, "LED panel Display")): str,
            }),
            errors=errors,
        )

    async def async_step_bluetooth(self, discovery_info) -> FlowResult:
        """Handle Bluetooth discovery."""
        address = discovery_info.address
        name = discovery_info.name or f"LED panel {address[-8:]}"

        # The discovery advertisement is the most reliable place to read the
        # product identity: the panel is by definition disconnected here, so
        # it is still broadcasting. Once it is connected it goes quiet.
        self._identity = parse_identity(
            getattr(discovery_info, "manufacturer_data", None)
        )
        
        # Check if already configured
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        
        # Set context for confirm step
        self.context["title_placeholders"] = {
            "name": name,
            "address": address,
        }
        
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Bluetooth discovery."""
        placeholders = self.context["title_placeholders"]
        
        if user_input is not None:
            try:
                # Test connection
                await validate_input(
                    self.hass,
                    {
                        CONF_ADDRESS: placeholders["address"],
                        CONF_NAME: placeholders["name"]
                    }
                )
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")
            except Exception:
                _LOGGER.exception("Unexpected exception during Bluetooth confirm")
                return self.async_abort(reason="unknown")
            
            return self.async_create_entry(
                title=placeholders["name"],
                data={
                    CONF_ADDRESS: placeholders["address"],
                    CONF_NAME: placeholders["name"],
                    **self._identity_data(),
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=placeholders,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for BLE LED Pixel Display.

    NOTE: do NOT define __init__(self, config_entry) and assign to
    self.config_entry — on modern HA (2024.12+), `config_entry` is a
    read-only property automatically populated by the framework, so
    overriding it raises ``AttributeError: ... has no setter``.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    OPT_OVERRIDE_DIMENSIONS,
                    default=current.get(OPT_OVERRIDE_DIMENSIONS, False),
                ): bool,
                vol.Optional(
                    OPT_PANEL_WIDTH,
                    default=current.get(OPT_PANEL_WIDTH, 0),
                ): vol.All(int, vol.Range(min=0, max=512)),
                vol.Optional(
                    OPT_PANEL_HEIGHT,
                    default=current.get(OPT_PANEL_HEIGHT, 0),
                ): vol.All(int, vol.Range(min=0, max=512)),
                vol.Optional(
                    OPT_FORCE_FEATURES,
                    default=current.get(OPT_FORCE_FEATURES, False),
                ): bool,
                # Only needed for a panel that was locked from the vendor app.
                # Masked, because it is a secret even if a short one.
                vol.Optional(
                    OPT_PASSWORD,
                    default=current.get(OPT_PASSWORD, ""),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )