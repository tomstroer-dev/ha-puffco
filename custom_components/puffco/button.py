"""Buttons for Puffco: start / stop a heat cycle, refresh."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    MC_HEAT_ABORT,
    MC_HEAT_START,
    MC_IDLE,
    PATH_ACTIVE_PROFILE,
    PATH_MODE_COMMAND,
    PROFILE_COUNT,
)
from .coordinator import PuffcoConfigEntry, PuffcoCoordinator
from .entity import PuffcoEntity
from .lorax import LoraxClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PuffcoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            PuffcoStartButton(coordinator),
            PuffcoStopButton(coordinator),
            PuffcoRefreshButton(coordinator),
        ]
    )


class PuffcoStartButton(PuffcoEntity, ButtonEntity):
    """Start a heat cycle with the selected profile."""

    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: PuffcoCoordinator) -> None:
        super().__init__(coordinator, "start_heat")

    async def async_press(self) -> None:
        profile = self.coordinator.selected_profile
        if profile is None or not 0 <= profile < PROFILE_COUNT:
            profile = 0

        async def _start(lorax: LoraxClient) -> None:
            await lorax.write_i8(PATH_ACTIVE_PROFILE, profile)
            await lorax.write_u8(PATH_MODE_COMMAND, MC_HEAT_START)

        await self.coordinator.async_run_command(_start)


class PuffcoStopButton(PuffcoEntity, ButtonEntity):
    """Abort a running heat cycle."""

    _attr_icon = "mdi:fire-off"

    def __init__(self, coordinator: PuffcoCoordinator) -> None:
        super().__init__(coordinator, "stop_heat")

    async def async_press(self) -> None:
        async def _stop(lorax: LoraxClient) -> None:
            await lorax.write_u8(PATH_MODE_COMMAND, MC_HEAT_ABORT)
            await lorax.write_u8(PATH_MODE_COMMAND, MC_IDLE)

        await self.coordinator.async_run_command(_stop)


class PuffcoRefreshButton(PuffcoEntity, ButtonEntity):
    """Poll the device now."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _sticky = True

    def __init__(self, coordinator: PuffcoCoordinator) -> None:
        super().__init__(coordinator, "refresh")

    @property
    def available(self) -> bool:
        return True

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
