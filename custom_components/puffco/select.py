"""Profile select: which heat profile the start button uses."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PROFILE_COUNT
from .coordinator import PuffcoConfigEntry, PuffcoCoordinator
from .entity import PuffcoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PuffcoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([PuffcoProfileSelect(entry.runtime_data)])


class PuffcoProfileSelect(PuffcoEntity, SelectEntity):
    """Choose the profile for the next heat cycle (stored in HA, not on the device)."""

    _attr_icon = "mdi:thermometer-lines"
    _sticky = True

    def __init__(self, coordinator: PuffcoCoordinator) -> None:
        super().__init__(coordinator, "start_profile")

    def _labels(self) -> list[str]:
        labels: list[str] = []
        for index in range(PROFILE_COUNT):
            label = self.coordinator.profile_name(index)
            # keep labels unique even if two profiles share a name
            if label in labels:
                label = f"{label} ({index + 1})"
            labels.append(label)
        return labels

    @property
    def options(self) -> list[str]:
        return self._labels()

    @property
    def current_option(self) -> str | None:
        index = self.coordinator.selected_profile
        if index is None or not 0 <= index < PROFILE_COUNT:
            return None
        return self._labels()[index]

    async def async_select_option(self, option: str) -> None:
        self.coordinator.selected_profile = self._labels().index(option)
        self.async_write_ha_state()
