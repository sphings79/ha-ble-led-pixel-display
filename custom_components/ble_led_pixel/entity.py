"""Device registration shared by every entity of a panel."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from .api import BleLedPixelAPI


def panel_device_info(api: "BleLedPixelAPI", address: str, name: str) -> DeviceInfo:
    """Build the device registration for a panel.

    The manufacturer is only named when the advertised product id maps to a
    brand we actually know. For everything else a neutral value is used rather
    than a guess - but a value nonetheless: Home Assistant keeps the previous
    registry entry when a field is omitted, so leaving it out would preserve
    whatever was written there before.

    The raw product id stays visible through the cidpid diagnostic sensor, so
    an unrecognised panel can still be identified and reported.
    """
    brand: str | None = None
    try:
        brand = api.identity.brand
    except Exception:  # noqa: BLE001 - registration must never break setup
        pass

    return DeviceInfo(
        identifiers={(DOMAIN, address)},
        name=name,
        manufacturer=brand or "LED_BLE",
        model="LED Pixel Panel",
        sw_version="1.0",
    )


_UNAVAILABLE = "unavailable"


class _LastGoodState:
    """The parts of a State that the entities' restore code reads."""

    def __init__(self, state: str, attributes: dict | None) -> None:
        self.state = state
        self.attributes = attributes or {}


class ModeScopedEntity:
    """A setting that only matters in some display modes.

    It shows as unavailable (greyed out) while the panel is in another mode,
    so the device page shows which settings the current mode uses.

    Home Assistant saves an unavailable entity's state as "unavailable", so a
    restart in another mode would lose the value. The value therefore also
    goes into the entity's extra restore data, and restoring falls back to
    it.

    List this mixin before the Home Assistant entity classes, so that its
    ``available`` and ``async_get_last_state`` are the ones used.
    """

    _modes: frozenset[str] = frozenset()

    @property
    def available(self) -> bool:
        mode = getattr(self._api, "current_mode", None)
        return mode is None or mode in self._modes

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        add_listener = getattr(self._api, "add_mode_listener", None)
        if add_listener is not None:
            self.async_on_remove(add_listener(self._mode_changed))

    def _mode_changed(self) -> None:
        if getattr(self, "hass", None) is not None and getattr(self, "entity_id", None):
            self.async_write_ha_state()

    @property
    def extra_restore_state_data(self):
        from homeassistant.helpers.restore_state import RestoredExtraData

        try:
            state = self.state
            attributes = dict(self.state_attributes or {})
        except Exception:  # noqa: BLE001 - never break saving the others
            return None
        if state is None:
            return None
        return RestoredExtraData(
            {"state": str(state), "attributes": _jsonable(attributes)}
        )

    async def async_get_last_state(self):
        last = await super().async_get_last_state()
        if last is not None and last.state != _UNAVAILABLE:
            return last
        extra = await self.async_get_last_extra_data()
        if extra is None:
            return last
        data = extra.as_dict()
        if not isinstance(data, dict) or "state" not in data:
            return last
        return _LastGoodState(data["state"], data.get("attributes"))


def _jsonable(attributes: dict) -> dict:
    """Tuples (RGB colours) become lists; other values pass through."""
    return {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in attributes.items()
    }
