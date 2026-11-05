"""Select entity for BLE LED Pixel Display font selection."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.restore_state import async_get as restore_state_data

from .api import BleLedPixelAPI
from .const import (
    ALL_TEXT_EFFECTS,
    AVAILABLE_MODES,
    CONF_ADDRESS,
    CONF_NAME,
    DEFAULT_MODE,
    DEFAULT_TEXT_EFFECT,
    DEFAULT_TEXT_GRADIENT,
    DEFAULT_TEXT_SIZE,
    DOMAIN,
    TEXT_EFFECTS,
    text_effects,
    TEXT_GRADIENTS,
    text_size_from_font_size,
)
from .device_types import clock_style_count
from .entity import panel_device_info
from .common import get_entity_id_by_unique_id
from .common import update_panel_display
from .fonts import get_available_fonts
from .gallery import Motif, async_load_gallery

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BLE LED Pixel Display select entities."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        BleLedPixelFontSelect(hass, api, entry, address, name),
        BleLedPixelModeSelect(hass, api, entry, address, name),
        BleLedPixelClockStyleSelect(hass, api, entry, address, name),
        BleLedPixelTextEffectSelect(hass, api, entry, address, name),
        BleLedPixelTextGradientSelect(hass, api, entry, address, name),
        BleLedPixelTextSizeSelect(hass, api, entry, address, name),
    ]

    # A select with no options is not something Home Assistant can render, so
    # the gallery entity only appears when there are pictures to offer.
    motifs = await async_load_gallery(hass)
    if motifs:
        entities.append(BleLedPixelGallerySelect(hass, api, entry, address, name, motifs))

    async_add_entities(entities)


class BleLedPixelFontSelect(SelectEntity, RestoreEntity):
    """Representation of an BLE LED Pixel Display font selection."""

    def __init__(
        self, 
        hass: HomeAssistant,
        api: BleLedPixelAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the font select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Font"
        self._attr_unique_id = f"{address}_font_select"

        # Get available fonts from all locations
        self._attr_options = get_available_fonts()
        self._attr_current_option = "OpenSans-Light.ttf" if "OpenSans-Light.ttf" in self._attr_options else self._attr_options[0]
        
        # Device info for grouping in device registry
        self._attr_device_info = panel_device_info(api, address, name)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Restore last state if available
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored font selection: %s", self._attr_current_option)

    @property
    def current_option(self) -> str | None:
        """Return the current selected font."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select a font option."""
        if option in self._attr_options:
            self._attr_current_option = option
            _LOGGER.debug("Font changed to: %s", option)
            
            # Trigger display update if auto-update is enabled
            await self._trigger_auto_update()
        else:
            _LOGGER.error("Invalid font option: %s", option)

    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled."""
        try:
            # Check auto-update setting
            auto_update_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
            auto_update_state = self.hass.states.get(auto_update_entity_id) if auto_update_entity_id else None
            
            if auto_update_state and auto_update_state.state == "on":
                # Use common update function directly
                await update_panel_display(self.hass, self._name, self._api)
                _LOGGER.debug("Auto-update triggered display refresh due to font change")
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True


class BleLedPixelModeSelect(SelectEntity, RestoreEntity):
    """Representation of an BLE LED Pixel Display mode selection."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BleLedPixelAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the mode select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Mode"
        self._attr_unique_id = f"{address}_mode_select"

        # Set available mode options
        self._attr_options = AVAILABLE_MODES
        self._attr_current_option = DEFAULT_MODE

        # Device info for grouping in device registry
        self._attr_device_info = panel_device_info(api, address, name)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore last state if available
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored mode selection: %s", self._attr_current_option)
        self._api.set_current_mode(self._attr_current_option)

    @property
    def current_option(self) -> str | None:
        """Return the current selected mode."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select a mode option."""
        if option in self._attr_options:
            self._attr_current_option = option
            _LOGGER.info("Mode changed to: %s", option)
            # Before the update: it reads the mode, and this select's state
            # in Home Assistant is only written after this handler returns.
            self._api.set_current_mode(option)

            # Trigger display update if auto-update is enabled
            await self._trigger_auto_update()
        else:
            _LOGGER.error("Invalid mode option: %s", option)

    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled."""
        try:
            # Check auto-update setting
            auto_update_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
            auto_update_state = self.hass.states.get(auto_update_entity_id) if auto_update_entity_id else None

            if auto_update_state and auto_update_state.state == "on":
                # Use common update function directly
                await update_panel_display(self.hass, self._name, self._api)
                _LOGGER.debug("Auto-update triggered display refresh due to mode change")
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True


class BleLedPixelClockStyleSelect(SelectEntity, RestoreEntity):
    """Representation of an BLE LED Pixel Display clock style selection."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BleLedPixelAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the clock style select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Clock Style"
        self._attr_unique_id = f"{address}_clock_style_select"
        # How many faces a panel offers depends on its resolution: most
        # have eight, a 32x32 has nine, a 32x16 ten, a 144x16 only six.
        # Offering one the panel does not have is another command it
        # would accept and then quietly ignore.
        info = api.device_info or {}
        count = clock_style_count(info.get("width"), info.get("height"))
        self._attr_options = [str(i) for i in range(count)]
        self._attr_current_option = "1"  # Default style

        # Device info for grouping in device registry
        self._attr_device_info = panel_device_info(api, address, name)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore last state if available
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored clock style selection: %s", self._attr_current_option)

    @property
    def current_option(self) -> str | None:
        """Return the current selected clock style."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select a clock style option."""
        if option in self._attr_options:
            self._attr_current_option = option
            _LOGGER.info("Clock style changed to: %s", option)

            # Trigger display update if auto-update is enabled and in clock mode
            await self._trigger_auto_update()
        else:
            _LOGGER.error("Invalid clock style option: %s", option)

    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled and in clock mode."""
        try:
            # Check if we're in clock mode
            mode_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "mode_select", "select")
            mode_state = self.hass.states.get(mode_entity_id) if mode_entity_id else None

            if mode_state and mode_state.state == "clock":
                # Check auto-update setting
                auto_update_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
                auto_update_state = self.hass.states.get(auto_update_entity_id) if auto_update_entity_id else None

                if auto_update_state and auto_update_state.state == "on":
                    # Use common update function directly
                    await update_panel_display(self.hass, self._name, self._api)
                    _LOGGER.debug("Auto-update triggered display refresh due to clock style change")
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

class BleLedPixelTextEffectSelect(SelectEntity, RestoreEntity):
    """How the panel animates text written to the text entity.

    The effect is a property of the text command, so it is picked here and
    applied the next time the display is refreshed - it is not a command of
    its own.
    """

    _attr_icon = "mdi:animation"

    def __init__(
        self,
        hass: HomeAssistant,
        api: BleLedPixelAPI,
        entry: ConfigEntry,
        address: str,
        name: str,
    ) -> None:
        """Initialize the text effect select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name

        self._attr_name = "Text Effect"
        self._attr_unique_id = f"{address}_text_effect_select"
        self._attr_current_option = DEFAULT_TEXT_EFFECT

        self._attr_device_info = panel_device_info(api, address, name)

    async def async_added_to_hass(self) -> None:
        """Restore the previous selection."""
        await super().async_added_to_hass()
        self.async_on_remove(self._api.add_device_info_listener(self._panel_info_known))
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        # Scroll up/down only while allowed -- or while the panel size is
        # still unknown, in which case _panel_info_known settles it.
        if last_state.state in self.options or (
            last_state.state in ALL_TEXT_EFFECTS and self._api.device_info is None
        ):
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored text effect: %s", self._attr_current_option)
            return
        # Migrating from the old number entity, which stored a bare code.
        try:
            code = int(float(last_state.state))
        except (TypeError, ValueError):
            return
        for name, value in text_effects(self._api.vertical_scroll_allowed).items():
            if value == code:
                self._attr_current_option = name
                _LOGGER.debug("Migrated text effect %s to %s", code, name)
                return

    @callback
    def _panel_info_known(self) -> None:
        """Publish the options for the now-known panel size."""
        if self._attr_current_option not in self.options:
            _LOGGER.info(
                "Text effect %s is not available on this panel; using %s",
                self._attr_current_option, DEFAULT_TEXT_EFFECT,
            )
            self._attr_current_option = DEFAULT_TEXT_EFFECT
        if self.hass is not None:
            self.async_write_ha_state()

    @property
    def options(self) -> list[str]:
        """Effects for this panel.

        Read each time, so a 32x32 panel that was out of reach at setup gains
        scroll up/down once its size is known.
        """
        return list(text_effects(self._api.vertical_scroll_allowed))

    @property
    def current_option(self) -> str | None:
        """Return the selected effect."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select an effect and refresh the display if it is showing text."""
        if option not in self.options:
            _LOGGER.error("Unknown text effect: %s", option)
            return
        self._attr_current_option = option
        _LOGGER.info("Text effect changed to: %s", option)
        await self._trigger_auto_update()

    async def _trigger_auto_update(self) -> None:
        """Refresh the panel when auto-update is on and it is showing text."""
        try:
            from .common import update_panel_display

            mode_entity_id = get_entity_id_by_unique_id(
                self.hass, self._address, "mode_select", "select"
            )
            mode_state = self.hass.states.get(mode_entity_id) if mode_entity_id else None
            if not mode_state or mode_state.state != "text":
                return

            auto_entity_id = get_entity_id_by_unique_id(
                self.hass, self._address, "auto_update", "switch"
            )
            auto_state = self.hass.states.get(auto_entity_id) if auto_entity_id else None
            if auto_state and auto_state.state == "on":
                await update_panel_display(self.hass, self._name, self._api)
                _LOGGER.debug("Auto-update refreshed the display for the new effect")
        except Exception as err:  # noqa: BLE001 - a refresh must not break the select
            _LOGGER.debug("Could not refresh after the effect change: %s", err)


class BleLedPixelTextGradientSelect(SelectEntity, RestoreEntity):
    """Colour gradient applied to text, the protocol's "rainbow mode".

    Off leaves the text in the colour picked by the text colour light. The
    panel renders the gradient itself; the labels describe the ramps rather
    than naming them, because the vendor numbers them and nothing more.
    """

    _attr_icon = "mdi:gradient-horizontal"

    def __init__(
        self,
        hass: HomeAssistant,
        api: BleLedPixelAPI,
        entry: ConfigEntry,
        address: str,
        name: str,
    ) -> None:
        """Initialize the gradient select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name

        self._attr_name = "Text Gradient"
        self._attr_unique_id = f"{address}_text_gradient_select"
        self._attr_options = list(TEXT_GRADIENTS)
        self._attr_current_option = DEFAULT_TEXT_GRADIENT

        self._attr_device_info = panel_device_info(api, address, name)

    async def async_added_to_hass(self) -> None:
        """Restore the previous selection."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        if last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
            return
        # Migrating from the old number entity, which stored a bare code.
        try:
            code = int(float(last_state.state))
        except (TypeError, ValueError):
            return
        for label, value in TEXT_GRADIENTS.items():
            if value == code:
                self._attr_current_option = label
                _LOGGER.debug("Migrated text gradient %s to %s", code, label)
                return

    @property
    def current_option(self) -> str | None:
        """Return the selected gradient."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select a gradient and refresh the display if it is showing text."""
        if option not in self._attr_options:
            _LOGGER.error("Unknown text gradient: %s", option)
            return
        self._attr_current_option = option
        _LOGGER.info("Text gradient changed to: %s", option)
        await self._trigger_auto_update()

    async def _trigger_auto_update(self) -> None:
        """Refresh the panel when auto-update is on and it is showing text."""
        try:
            from .common import update_panel_display

            mode_entity_id = get_entity_id_by_unique_id(
                self.hass, self._address, "mode_select", "select"
            )
            mode_state = self.hass.states.get(mode_entity_id) if mode_entity_id else None
            if not mode_state or mode_state.state != "text":
                return

            auto_entity_id = get_entity_id_by_unique_id(
                self.hass, self._address, "auto_update", "switch"
            )
            auto_state = self.hass.states.get(auto_entity_id) if auto_entity_id else None
            if auto_state and auto_state.state == "on":
                await update_panel_display(self.hass, self._name, self._api)
        except Exception as err:  # noqa: BLE001 - a refresh must not break the select
            _LOGGER.debug("Could not refresh after the gradient change: %s", err)


async def _refresh_if_showing_text(hass: HomeAssistant, address: str, name: str, api: BleLedPixelAPI) -> None:
    """Refresh the panel when auto-update is on and it is in text mode."""
    mode_entity_id = get_entity_id_by_unique_id(hass, address, "mode_select", "select")
    mode_state = hass.states.get(mode_entity_id) if mode_entity_id else None
    if not mode_state or mode_state.state != "text":
        return
    auto_entity_id = get_entity_id_by_unique_id(hass, address, "auto_update", "switch")
    auto_state = hass.states.get(auto_entity_id) if auto_entity_id else None
    if auto_state and auto_state.state == "on":
        await update_panel_display(hass, name, api)


def _stored_state(hass: HomeAssistant, entity_id: str):
    """The state saved at shutdown for an entity, across HA versions.

    Older releases index saved states by entity id in ``last_states``; newer
    ones keep registered entities under their registry id instead.
    """
    data = restore_state_data(hass)
    by_entity_id = getattr(data, "last_states", None)
    if by_entity_id is None:
        by_entity_id = getattr(data, "last_states_by_entity_id", {})
    stored = by_entity_id.get(entity_id)
    by_registry_id = getattr(data, "last_states_by_entity_registry_id", None)
    if stored is None and by_registry_id is not None:
        entry = er.async_get(hass).async_get(entity_id)
        if entry is not None:
            stored = by_registry_id.get(entry.id)
    return stored


class BleLedPixelTextSizeSelect(SelectEntity, RestoreEntity):
    """Character height in text mode.

    The panel draws text mode itself, in whole 16px rows, so only 16, 32, 48
    and 64 differ, and only the ones that fit the panel are offered. The
    finer-grained Image Font Size number is for the textimage mode, which
    this integration renders itself.

    On the first start after upgrading, the size is taken from what the
    Image Font Size number amounted to in text mode, so text looks the same
    as before.
    """

    _attr_icon = "mdi:format-size"

    def __init__(
        self,
        hass: HomeAssistant,
        api: BleLedPixelAPI,
        entry: ConfigEntry,
        address: str,
        name: str,
    ) -> None:
        """Initialize the text size select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Text Size"
        self._attr_unique_id = f"{address}_text_size_select"
        self._chosen: int | None = None
        self._attr_device_info = panel_device_info(api, address, name)

    @property
    def options(self) -> list[str]:
        """Sizes that fit the panel."""
        return [str(size) for size in self._api.text_sizes]

    @property
    def size(self) -> int:
        """The size text mode uses, always one the panel can show."""
        sizes = self._api.text_sizes
        wanted = self._chosen if self._chosen is not None else DEFAULT_TEXT_SIZE
        fitting = [size for size in sizes if size <= wanted]
        return fitting[-1] if fitting else sizes[0]

    @property
    def current_option(self) -> str | None:
        """Return the size in use."""
        return str(self.size)

    async def async_added_to_hass(self) -> None:
        """Restore the previous selection, or migrate from the number."""
        await super().async_added_to_hass()
        self.async_on_remove(self._api.add_device_info_listener(self._panel_info_known))
        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                self._chosen = int(last_state.state)
                return
            except (TypeError, ValueError):
                pass
        self._chosen = self._migrated_size()

    @callback
    def _panel_info_known(self) -> None:
        """Publish the sizes that fit, now that the panel height is known."""
        if self.hass is not None:
            self.async_write_ha_state()

    def _migrated_size(self) -> int:
        """Text size the Image Font Size number gave text mode before 2.4.

        Read from the saved state rather than the live one, because the
        number platform is set up after this one.
        """
        entity_id = get_entity_id_by_unique_id(self.hass, self._address, "font_size", "number")
        if not entity_id:
            return DEFAULT_TEXT_SIZE
        try:
            stored = _stored_state(self.hass, entity_id)
            value = float(stored.state.state) if stored else None
        except Exception:  # noqa: BLE001 - internal API; losing the migration is fine
            value = None
        size = text_size_from_font_size(value)
        if size != DEFAULT_TEXT_SIZE:
            _LOGGER.info("Text size set to %spx from the old Font Size", size)
        return size

    async def async_select_option(self, option: str) -> None:
        """Pick a size and refresh the display if it is showing text."""
        if option not in self.options:
            _LOGGER.error("Text size %s does not fit this panel", option)
            return
        self._chosen = int(option)
        self.async_write_ha_state()
        _LOGGER.info("Text size changed to: %s", option)
        try:
            await _refresh_if_showing_text(self.hass, self._address, self._name, self._api)
        except Exception as err:  # noqa: BLE001 - a refresh must not break the select
            _LOGGER.debug("Could not refresh after the text size change: %s", err)


class BleLedPixelGallerySelect(SelectEntity, RestoreEntity):
    """Pick one of the bundled pictures and send it straight to the panel.

    This is the shortest path from "I want a picture up there" to a picture
    being up there: no file paths, no service call, just a dropdown on the
    device page that also works as an automation target.
    """

    _attr_icon = "mdi:image-multiple"

    def __init__(
        self,
        hass: HomeAssistant,
        api: BleLedPixelAPI,
        entry: ConfigEntry,
        address: str,
        name: str,
        motifs: list[Motif],
    ) -> None:
        """Initialize the gallery select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._motifs = motifs
        self._attr_name = "Gallery"
        self._attr_unique_id = f"{address}_gallery_select"
        self._attr_options = [motif.label for motif in motifs]
        self._attr_current_option = None
        self._attr_device_info = panel_device_info(api, address, name)

    async def async_added_to_hass(self) -> None:
        """Restore which picture was picked last, without re-sending it."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state

    @property
    def current_option(self) -> str | None:
        """Return the picture picked last."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Send the chosen picture to the panel."""
        if option not in self._attr_options:
            _LOGGER.error("Unknown gallery picture: %s", option)
            return

        if await self._api.show_gallery_image(option):
            self._attr_current_option = option
            self.async_write_ha_state()
        else:
            _LOGGER.error("Could not send gallery picture %s to the panel", option)
