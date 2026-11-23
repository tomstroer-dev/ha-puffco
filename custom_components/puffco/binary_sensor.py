"""Binary sensors for Puffco."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CHARGING_STATES
from .coordinator import PuffcoConfigEntry, PuffcoCoordinator
from .entity import PuffcoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PuffcoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            PuffcoHeatingSensor(coordinator),
            PuffcoChargingSensor(coordinator),
            PuffcoReachableSensor(coordinator),
        ]
    )


class PuffcoHeatingSensor(PuffcoEntity, BinarySensorEntity):
    """True while a heat cycle runs (preheat, active, fade)."""

    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(self, coordinator: PuffcoCoordinator) -> None:
        super().__init__(coordinator, "heating")

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return data.heating if data and data.state is not None else None


class PuffcoChargingSensor(PuffcoEntity, BinarySensorEntity):
    """True while the battery charges."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _sticky = True

    def __init__(self, coordinator: PuffcoCoordinator) -> None:
        super().__init__(coordinator, "charging")

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if not data or data.charge_state is None:
            return None
        return data.charge_state in CHARGING_STATES


class PuffcoReachableSensor(PuffcoEntity, BinarySensorEntity):
    """Whether the last poll reached the device."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PuffcoCoordinator) -> None:
        super().__init__(coordinator, "reachable")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success
