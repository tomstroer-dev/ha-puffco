"""Constants for the Puffco integration."""

from __future__ import annotations

DOMAIN = "puffco"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 300  # seconds, when idle
HEATING_SCAN_INTERVAL = 15  # seconds, while a heat cycle runs
MIN_SCAN_INTERVAL = 60

# --- Lorax BLE service -----------------------------------------------------
LORAX_SERVICE_UUID = "e276967f-ea8a-478a-a92e-d78f5dd15dd5"
LORAX_VERSION_CHAR = "05434bca-cc7f-4ef6-bbb3-b1c520b9800c"
LORAX_COMMAND_CHAR = "60133d5c-5727-4f2c-9697-d842c5292a3c"
LORAX_REPLY_CHAR = "8dc5ec05-8f7d-45ad-99db-3fbde65dbd9c"

# Handshake secret used by the official app for "lorax" firmware.
LORAX_KEY_B64 = "ZMZFYlbyb1scoSc3pd1x+w=="

OP_GET_ACCESS_SEED = 0x00
OP_UNLOCK_ACCESS = 0x01
OP_GET_LIMITS = 0x02
OP_READ_SHORT = 0x10
OP_WRITE_SHORT = 0x11

WRITE_FLAG_TRUNCATE = 0x04

# --- Paths -----------------------------------------------------------------
PATH_NAME = "/u/sys/name"
PATH_SERIAL = "/p/sys/hw/ser"
PATH_FW_HASH = "/p/sys/fw/gith"
PATH_FW_API = "/p/sys/fw/api"
PATH_BATTERY = "/p/bat/soc"
PATH_CHARGE_STATE = "/p/bat/chg/stat"
PATH_CHARGE_ETF = "/p/bat/chg/etf"
PATH_HEATER_TEMP = "/p/app/htr/temp"
PATH_STATE = "/p/app/stat/id"
PATH_STATE_ELAPSED = "/p/app/stat/elap"
PATH_STATE_TOTAL = "/p/app/stat/tott"
PATH_ACTIVE_PROFILE = "/p/app/hcs"
PATH_DABS_TOTAL = "/p/app/odom/0/nc"
PATH_DABS_TOTAL_ALT = "/p/app/info/dtot"
PATH_DABS_PER_DAY = "/p/app/info/dpd"
PATH_DABS_REMAINING = "/p/app/info/drem"
PATH_CHAMBER = "/p/htr/chmt"
PATH_MODE_COMMAND = "/p/app/mc"
PATH_LANTERN_CMD = "/p/app/ltrn/cmd"
PATH_PROFILE = "/u/app/hc/{index}/{leaf}"

PROFILE_COUNT = 4

# --- Mode commands -----------------------------------------------------------
MC_IDLE = 2
MC_HEAT_START = 7
MC_HEAT_ABORT = 8

# --- Enums -------------------------------------------------------------------
OPERATING_STATES: dict[int, str] = {
    0: "init",
    1: "init",
    2: "init",
    3: "master_off",
    4: "sleep",
    5: "idle",
    6: "temp_select",
    7: "preheat",
    8: "active",
    9: "fade",
    10: "version_display",
    11: "battery_display",
    12: "factory_test",
    13: "bonding",
}
HEATING_STATES = {7, 8, 9}

CHARGE_STATES: dict[int, str] = {
    0: "charging",
    1: "topping_up",
    2: "full",
    3: "paused_temperature",
    4: "not_charging",
}
CHARGING_STATES = {0, 1}

CHAMBER_TYPES: dict[int, str] = {
    0: "none",
    1: "standard",
    2: "xl_v1",
    3: "three_d",
    4: "three_d_xl",
    5: "proxy_3d",
}
