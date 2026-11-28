"""Config flow for Puffco."""

from __future__ import annotations

import logging
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LORAX_SERVICE_UUID,
    MIN_SCAN_INTERVAL,
    PATH_NAME,
)
from .lorax import LoraxClient, LoraxError, LoraxTimeout

_LOGGER = logging.getLogger(__name__)

_NAME_PREFIXES = ("peak", "puffco")


def _is_puffco(info: BluetoothServiceInfoBleak) -> bool:
    if LORAX_SERVICE_UUID in [u.lower() for u in info.service_uuids]:
        return True
    name = (info.name or "").lower()
    return any(part in name for part in _NAME_PREFIXES)


class PuffcoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Puffco."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PuffcoOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Device found via Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if not _is_puffco(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_pair()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a discovered Puffco."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._discovery = self._discovered[address]
            return await self.async_step_pair()

        current = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current or not _is_puffco(info):
                continue
            self._discovered[info.address] = info
        if not self._discovered:
            # Renamed devices ("Erol's ...") may not match by name or UUID:
            # fall back to every connectable device that advertises a name.
            for info in async_discovered_service_info(self.hass, connectable=True):
                if info.address in current or not info.name:
                    continue
                if info.name.replace("-", ":").upper() == info.address.upper():
                    continue
                self._discovered[info.address] = info
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            addr: f"{info.name or 'Puffco'} ({addr})"
                            for addr, info in self._discovered.items()
                        }
                    )
                }
            ),
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to put the Puffco into pairing mode, then test it."""
        assert self._discovery is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            name, error = await self._async_test_device(self._discovery.address)
            if error is None:
                return self.async_create_entry(
                    title=name or self._discovery.name or "Puffco",
                    data={CONF_ADDRESS: self._discovery.address},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="pair",
            description_placeholders={"name": self._discovery.name or "Puffco"},
            errors=errors,
        )

    async def _async_test_device(self, address: str) -> tuple[str | None, str | None]:
        """Connect, pair, authenticate. Returns (device name, error key)."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, address, connectable=True
        )
        if ble_device is None:
            return None, "not_in_range"
        try:
            client = await establish_connection(
                BleakClientWithServiceCache, ble_device, "Puffco", max_attempts=3
            )
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug("Connect failed: %s", err)
            return None, "cannot_connect"

        lorax = LoraxClient(client)
        try:
            try:
                await client.pair()
            except (BleakError, NotImplementedError, TimeoutError) as err:
                _LOGGER.debug("Pairing call failed (may already be paired): %s", err)
            await lorax.start()
            await lorax.trigger_bonding()
            await lorax.authenticate()
            return await lorax.read_str(PATH_NAME), None
        except LoraxTimeout:
            return None, "not_paired"
        except (LoraxError, BleakError, TimeoutError, EOFError) as err:
            _LOGGER.debug("Auth failed: %s", err)
            return None, "auth_failed"
        finally:
            await lorax.stop()
            try:
                await client.disconnect()
            except (BleakError, EOFError, OSError):
                pass


class PuffcoOptionsFlow(OptionsFlow):
    """Options: poll interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)
                    )
                }
            ),
        )
