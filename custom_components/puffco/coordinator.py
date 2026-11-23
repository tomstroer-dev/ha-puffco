"""Data coordinator for the Puffco integration.

The Puffco only allows one central at a time, so the coordinator connects,
reads everything, and disconnects again. That keeps the official app usable
between polls.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakNotFoundError,
    establish_connection,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HEATING_SCAN_INTERVAL,
    HEATING_STATES,
    PATH_ACTIVE_PROFILE,
    PATH_BATTERY,
    PATH_CHAMBER,
    PATH_CHARGE_ETF,
    PATH_CHARGE_STATE,
    PATH_DABS_PER_DAY,
    PATH_DABS_REMAINING,
    PATH_DABS_TOTAL,
    PATH_DABS_TOTAL_ALT,
    PATH_FW_API,
    PATH_FW_HASH,
    PATH_HEATER_TEMP,
    PATH_NAME,
    PATH_PROFILE,
    PATH_SERIAL,
    PATH_STATE,
    PATH_STATE_ELAPSED,
    PATH_STATE_TOTAL,
    PROFILE_COUNT,
)
from .lorax import LoraxClient, LoraxError, LoraxTimeout

_LOGGER = logging.getLogger(__name__)

type PuffcoConfigEntry = ConfigEntry["PuffcoCoordinator"]


@dataclass
class PuffcoProfile:
    """One of the four heat profiles."""

    name: str | None = None
    temperature: float | None = None  # °C
    duration: float | None = None  # s


@dataclass
class PuffcoData:
    """Snapshot of the device state."""

    device_name: str | None = None
    serial: str | None = None
    firmware: str | None = None
    api_series: int | None = None
    battery: float | None = None
    charge_state: int | None = None
    charge_time_to_full: float | None = None
    heater_temp: float | None = None
    state: int | None = None
    state_elapsed: float | None = None
    state_total: float | None = None
    active_profile: int | None = None
    dabs_total: float | None = None
    dabs_per_day: float | None = None
    dabs_remaining: float | None = None
    chamber: int | None = None
    profiles: list[PuffcoProfile] = field(default_factory=list)

    @property
    def heating(self) -> bool:
        return self.state in HEATING_STATES


class PuffcoCoordinator(DataUpdateCoordinator[PuffcoData]):
    """Polls the Puffco over BLE."""

    config_entry: PuffcoConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PuffcoConfigEntry) -> None:
        self.address: str = entry.data[CONF_ADDRESS]
        self._idle_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.address}",
            update_interval=self._idle_interval,
        )
        self._ble_lock = asyncio.Lock()
        self._paired_attempted = False
        self.selected_profile: int | None = None
        self.lantern_on: bool | None = None

    # ------------------------------------------------------------ connection
    async def _with_device(
        self, action: Callable[[LoraxClient], Awaitable[Any]]
    ) -> Any:
        """Connect, authenticate, run `action`, disconnect."""
        async with self._ble_lock:
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_device is None:
                raise UpdateFailed(
                    "Puffco nicht in Bluetooth-Reichweite oder im Schlafmodus"
                )
            try:
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self.config_entry.title,
                    max_attempts=3,
                )
            except (BleakNotFoundError, BleakError, TimeoutError) as err:
                raise UpdateFailed(f"Verbindung fehlgeschlagen: {err}") from err

            lorax = LoraxClient(client)
            try:
                await lorax.start()
                await lorax.trigger_bonding()
                try:
                    await lorax.authenticate()
                except LoraxTimeout:
                    # Most likely the link is not bonded/encrypted yet.
                    if self._paired_attempted:
                        raise
                    self._paired_attempted = True
                    _LOGGER.info("No Lorax reply, trying to pair with %s", self.address)
                    try:
                        await client.pair()
                    except NotImplementedError as err:
                        raise UpdateFailed(
                            "Koppeln über diesen Bluetooth-Adapter nicht möglich"
                        ) from err
                    await lorax.authenticate()
                return await action(lorax)
            except LoraxTimeout as err:
                raise UpdateFailed(
                    "Puffco antwortet nicht. Ist er gekoppelt? Logo-Knopf halten, "
                    "bis es blau leuchtet, dann neu laden."
                ) from err
            except (LoraxError, BleakError, TimeoutError, EOFError) as err:
                raise UpdateFailed(f"Bluetooth-Fehler: {err}") from err
            finally:
                await lorax.stop()
                try:
                    await client.disconnect()
                except (BleakError, EOFError, OSError):
                    pass

    # ---------------------------------------------------------------- polling
    async def _async_update_data(self) -> PuffcoData:
        previous = self.data
        data: PuffcoData = await self._with_device(
            lambda lorax: self._read_all(lorax, previous)
        )
        # Poll faster while a heat cycle is running.
        self.update_interval = (
            timedelta(seconds=HEATING_SCAN_INTERVAL)
            if data.heating
            else self._idle_interval
        )
        if self.selected_profile is None and data.active_profile in range(
            PROFILE_COUNT
        ):
            self.selected_profile = data.active_profile
        return data

    async def _read_all(
        self, lorax: LoraxClient, previous: PuffcoData | None
    ) -> PuffcoData:
        data = PuffcoData()

        # Static info: read once, then reuse.
        if previous and previous.serial:
            data.device_name = previous.device_name
            data.serial = previous.serial
            data.firmware = previous.firmware
            data.api_series = previous.api_series
        else:
            data.device_name = await lorax.read_str(PATH_NAME)
            data.serial = await lorax.read_str(PATH_SERIAL)
            data.firmware = await lorax.read_str(PATH_FW_HASH)
            api = await lorax.read_u32(PATH_FW_API)
            data.api_series = api >> 16 if api is not None else None
            if data.api_series not in (None, 0):
                _LOGGER.warning(
                    "Puffco API series %s detected; this integration is built "
                    "for the Peak Pro (series 0), values may be off",
                    data.api_series,
                )

        data.battery = await lorax.read_float(PATH_BATTERY)
        data.charge_state = await lorax.read_u8(PATH_CHARGE_STATE)
        data.charge_time_to_full = await lorax.read_float(PATH_CHARGE_ETF)
        data.heater_temp = await lorax.read_float(PATH_HEATER_TEMP)
        data.state = await lorax.read_u8(PATH_STATE)
        data.state_elapsed = await lorax.read_float(PATH_STATE_ELAPSED)
        data.state_total = await lorax.read_float(PATH_STATE_TOTAL)
        data.active_profile = await lorax.read_i8(PATH_ACTIVE_PROFILE)
        data.chamber = await lorax.read_u8(PATH_CHAMBER)

        dabs = await lorax.read_float(PATH_DABS_TOTAL)
        if dabs is None:
            alt = await lorax.read_u32(PATH_DABS_TOTAL_ALT)
            dabs = float(alt) if alt is not None else None
        data.dabs_total = dabs
        data.dabs_per_day = await lorax.read_float(PATH_DABS_PER_DAY)
        data.dabs_remaining = await lorax.read_float(PATH_DABS_REMAINING)

        # Profiles change rarely: refresh them only when idle or on first read.
        if previous and previous.profiles and data.heating:
            data.profiles = previous.profiles
        else:
            for index in range(PROFILE_COUNT):
                data.profiles.append(
                    PuffcoProfile(
                        name=await lorax.read_str(
                            PATH_PROFILE.format(index=index, leaf="name")
                        ),
                        temperature=await lorax.read_float(
                            PATH_PROFILE.format(index=index, leaf="temp")
                        ),
                        duration=await lorax.read_float(
                            PATH_PROFILE.format(index=index, leaf="time")
                        ),
                    )
                )
        return data

    # --------------------------------------------------------------- commands
    async def async_run_command(
        self, action: Callable[[LoraxClient], Awaitable[Any]]
    ) -> None:
        """Run a write action, then refresh shortly after."""
        try:
            await self._with_device(action)
        except UpdateFailed as err:
            raise HomeAssistantError(str(err)) from err
        await asyncio.sleep(1.5)
        await self.async_refresh()

    def profile_name(self, index: int) -> str:
        """Display name of a profile."""
        if self.data and index < len(self.data.profiles):
            name = self.data.profiles[index].name
            if name:
                return name
        return f"Profil {index + 1}"
