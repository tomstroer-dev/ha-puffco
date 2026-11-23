"""Base entity for Puffco."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PuffcoCoordinator


class PuffcoEntity(CoordinatorEntity[PuffcoCoordinator]):
    """Common Puffco entity."""

    _attr_has_entity_name = True
    # Live values (state, temperature) go unavailable when the device can't be
    # reached; "sticky" values (battery, counters, profiles) keep the last read.
    _sticky = False

    def __init__(self, coordinator: PuffcoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_translation_key = key
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            manufacturer="Puffco",
            model="Peak Pro",
            name=coordinator.config_entry.title,
            serial_number=data.serial if data else None,
            sw_version=data.firmware if data else None,
        )

    @property
    def available(self) -> bool:
        if self.coordinator.data is None:
            return False
        if self._sticky:
            return True
        return self.coordinator.last_update_success
