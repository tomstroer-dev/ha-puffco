"""Lantern (mood light) switch for Puffco.

The device has no documented read-back for the lantern, so the switch is
optimistic (assumed state).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PATH_LANTERN_CMD
from .coordinator import PuffcoConfigEntry, PuffcoCoordinator
from .entity import PuffcoEntity
from .lorax import LoraxClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PuffcoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([PuffcoLanternSwitch(entry.runtime_data)])


class PuffcoLanternSwitch(PuffcoEntity, SwitchEntity):
    """Lantern mode on/off."""

    _attr_assumed_state = True
    _attr_icon = "mdi:lightbulb-night"

    def __init__(self, coordinator: PuffcoCoordinator) -> None:
        super().__init__(coordinator, "lantern")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.lantern_on

    async def _set(self, on: bool) -> None:
        async def _write(lorax: LoraxClient) -> None:
            await lorax.write_u8(PATH_LANTERN_CMD, 1 if on else 0)

        await self.coordinator.async_run_command(_write)
        self.coordinator.lantern_on = on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
