"""Sensors for Puffco."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CHAMBER_TYPES, CHARGE_STATES, OPERATING_STATES
from .coordinator import PuffcoConfigEntry, PuffcoCoordinator, PuffcoData
from .entity import PuffcoEntity


def _round(value: float | None, digits: int = 0) -> float | None:
    if value is None:
        return None
    return round(value, digits) if digits else round(value)


def _profile(data: PuffcoData, attr: str) -> float | None:
    if data.active_profile is None or not 0 <= data.active_profile < len(data.profiles):
        return None
    return getattr(data.profiles[data.active_profile], attr)


def _remaining(data: PuffcoData) -> float | None:
    if not data.heating or data.state_total is None or data.state_elapsed is None:
        return None
    return max(0, round(data.state_total - data.state_elapsed))


@dataclass(frozen=True, kw_only=True)
class PuffcoSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PuffcoData], float | str | None]
    sticky: bool = False


SENSORS: tuple[PuffcoSensorDescription, ...] = (
    PuffcoSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _round(d.battery),
        sticky=True,
    ),
    PuffcoSensorDescription(
        key="charge_state",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(CHARGE_STATES.values())),
        value_fn=lambda d: CHARGE_STATES.get(d.charge_state)
        if d.charge_state is not None
        else None,
        sticky=True,
    ),
    PuffcoSensorDescription(
        key="charge_time_to_full",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: round(d.charge_time_to_full / 60)
        if d.charge_time_to_full and d.charge_time_to_full > 0
        else None,
        entity_registry_enabled_default=False,
    ),
    PuffcoSensorDescription(
        key="heater_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _round(d.heater_temp),
    ),
    PuffcoSensorDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(OPERATING_STATES.values())),
        value_fn=lambda d: OPERATING_STATES.get(d.state) if d.state is not None else None,
    ),
    PuffcoSensorDescription(
        key="session_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=_remaining,
    ),
    PuffcoSensorDescription(
        key="active_profile",
        value_fn=lambda d: (
            (d.profiles[d.active_profile].name or f"Profil {d.active_profile + 1}")
            if d.active_profile is not None and 0 <= d.active_profile < len(d.profiles)
            else None
        ),
        sticky=True,
    ),
    PuffcoSensorDescription(
        key="profile_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: _round(_profile(d, "temperature")),
        sticky=True,
    ),
    PuffcoSensorDescription(
        key="profile_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda d: _round(_profile(d, "duration")),
        sticky=True,
    ),
    PuffcoSensorDescription(
        key="dabs_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="Dabs",
        value_fn=lambda d: int(d.dabs_total) if d.dabs_total is not None else None,
        sticky=True,
    ),
    PuffcoSensorDescription(
        key="dabs_per_day",
        native_unit_of_measurement="Dabs",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _round(d.dabs_per_day, 1),
        sticky=True,
    ),
    PuffcoSensorDescription(
        key="dabs_remaining",
        native_unit_of_measurement="Dabs",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _round(d.dabs_remaining),
        sticky=True,
    ),
    PuffcoSensorDescription(
        key="chamber",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(CHAMBER_TYPES.values())),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: CHAMBER_TYPES.get(d.chamber) if d.chamber is not None else None,
        sticky=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PuffcoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PuffcoSensor(coordinator, desc) for desc in SENSORS)


class PuffcoSensor(PuffcoEntity, SensorEntity):
    """A Puffco sensor."""

    entity_description: PuffcoSensorDescription

    def __init__(
        self, coordinator: PuffcoCoordinator, description: PuffcoSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._sticky = description.sticky

    @property
    def native_value(self) -> float | str | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
