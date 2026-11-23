"""Minimal client for the Puffco "Lorax" BLE protocol (Peak Pro).

Protocol notes (from public reverse-engineering work, see README):
  request  = seq(u16 LE) + opcode(u8) + payload          -> COMMAND char
  reply    = seq(u16 LE) + status(u8, 0 = ok) + data     <- REPLY char (notify)
  auth     = token = SHA256(LORAX_KEY + seed[:16])[:16]
  readShort  payload = offset(u16) maxLen(u16) path
  writeShort payload = offset(u16) flags(u8) path 0x00 data
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import struct
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError

from .const import (
    LORAX_COMMAND_CHAR,
    LORAX_KEY_B64,
    LORAX_REPLY_CHAR,
    LORAX_VERSION_CHAR,
    OP_GET_ACCESS_SEED,
    OP_GET_LIMITS,
    OP_READ_SHORT,
    OP_UNLOCK_ACCESS,
    OP_WRITE_SHORT,
    WRITE_FLAG_TRUNCATE,
)

_LOGGER = logging.getLogger(__name__)

_LORAX_KEY = base64.b64decode(LORAX_KEY_B64)


class LoraxError(Exception):
    """Device answered with a non-zero status."""


class LoraxTimeout(Exception):
    """Device did not answer (usually: link not paired/encrypted)."""


def make_auth_token(seed: bytes) -> bytes:
    """Return the 16 byte unlock token for an access seed."""
    return hashlib.sha256(_LORAX_KEY + bytes(seed[:16])).digest()[:16]


class LoraxClient:
    """Talks Lorax over an already connected BleakClient."""

    def __init__(self, client: BleakClient) -> None:
        self._client = client
        self._seq = 0
        self._pending: dict[int, asyncio.Future[bytes]] = {}
        self._lock = asyncio.Lock()
        self.max_payload = 125

    # ------------------------------------------------------------------ setup
    async def start(self) -> None:
        """Subscribe to replies."""
        await self._client.start_notify(LORAX_REPLY_CHAR, self._on_reply)

    async def stop(self) -> None:
        """Unsubscribe (best effort)."""
        try:
            await self._client.stop_notify(LORAX_REPLY_CHAR)
        except (BleakError, EOFError, AttributeError, OSError):
            pass
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    async def trigger_bonding(self) -> None:
        """Reading the (encrypted) version characteristic triggers bonding."""
        try:
            await self._client.read_gatt_char(LORAX_VERSION_CHAR)
        except (BleakError, OSError) as err:
            _LOGGER.debug("Reading version characteristic failed: %s", err)

    async def authenticate(self) -> None:
        """Run the access-seed / unlock handshake."""
        try:
            limits = await self._transact(OP_GET_LIMITS, timeout=3.0)
            if len(limits) >= 2:
                max_payload = struct.unpack_from("<H", limits, 0)[0]
                if 16 <= max_payload <= 512:
                    self.max_payload = min(max_payload, 240)
        except LoraxError:
            pass
        seed = await self._transact(OP_GET_ACCESS_SEED)
        if len(seed) < 16:
            raise LoraxError(f"short access seed ({len(seed)} bytes)")
        await self._transact(OP_UNLOCK_ACCESS, make_auth_token(seed))

    # ------------------------------------------------------------- transport
    def _on_reply(self, _char: Any, data: bytearray) -> None:
        if len(data) < 3:
            return
        seq = struct.unpack_from("<H", data, 0)[0]
        status = data[2]
        fut = self._pending.pop(seq, None)
        if fut is None or fut.done():
            return
        if status:
            fut.set_exception(LoraxError(f"status {status}"))
        else:
            fut.set_result(bytes(data[3:]))

    async def _transact(
        self, opcode: int, payload: bytes = b"", timeout: float = 5.0
    ) -> bytes:
        async with self._lock:
            self._seq = (self._seq + 1) & 0xFFFF or 1
            seq = self._seq
            fut: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
            self._pending[seq] = fut
            frame = struct.pack("<HB", seq, opcode) + payload
            try:
                await self._client.write_gatt_char(
                    LORAX_COMMAND_CHAR, frame, response=False
                )
                return await asyncio.wait_for(fut, timeout)
            except asyncio.TimeoutError as err:
                raise LoraxTimeout(f"no reply to opcode 0x{opcode:02x}") from err
            finally:
                self._pending.pop(seq, None)

    # ------------------------------------------------------------ read/write
    async def read(self, path: str, max_len: int | None = None) -> bytes:
        size = min(max_len or self.max_payload, self.max_payload)
        payload = struct.pack("<HH", 0, size) + path.encode("ascii")
        return await self._transact(OP_READ_SHORT, payload)

    async def write(self, path: str, data: bytes) -> None:
        payload = (
            struct.pack("<HB", 0, WRITE_FLAG_TRUNCATE)
            + path.encode("ascii")
            + b"\x00"
            + bytes(data)
        )
        await self._transact(OP_WRITE_SHORT, payload)

    # ------------------------------------------------------- typed helpers
    async def read_float(self, path: str) -> float | None:
        data = await self._safe_read(path, 4)
        if data is None or len(data) < 4:
            return None
        return struct.unpack_from("<f", data, 0)[0]

    async def read_u8(self, path: str) -> int | None:
        data = await self._safe_read(path, 1)
        return data[0] if data else None

    async def read_i8(self, path: str) -> int | None:
        data = await self._safe_read(path, 1)
        return struct.unpack_from("<b", data, 0)[0] if data else None

    async def read_u32(self, path: str) -> int | None:
        data = await self._safe_read(path, 4)
        if data is None or len(data) < 4:
            return None
        return struct.unpack_from("<I", data, 0)[0]

    async def read_str(self, path: str) -> str | None:
        data = await self._safe_read(path, 64)
        if data is None:
            return None
        return data.split(b"\x00")[0].decode("latin1", "replace").strip() or None

    async def _safe_read(self, path: str, size: int) -> bytes | None:
        """Read a path; a status error means "not supported" and returns None."""
        try:
            return await self.read(path, size)
        except LoraxError as err:
            _LOGGER.debug("Read %s failed: %s", path, err)
            return None

    async def write_u8(self, path: str, value: int) -> None:
        await self.write(path, bytes([value & 0xFF]))

    async def write_i8(self, path: str, value: int) -> None:
        await self.write(path, struct.pack("<b", value))
