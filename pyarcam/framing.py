"""Binary frame packing and parsing for Arcam SA10/SA20."""

from __future__ import annotations

from dataclasses import dataclass

from pyarcam.constants import END_BYTE, START_BYTE
from pyarcam.exceptions import ArcamProtocolError


@dataclass(frozen=True)
class ResponseFrame:
    """Parsed amplifier → controller message."""

    zone: int
    command: int
    answer_code: int
    data: bytes


def pack_command(zone: int, command: int, data: bytes) -> bytes:
    """Build a controller → amplifier command frame."""
    if not 0 <= zone <= 0xFF:
        raise ValueError("zone out of range")
    if not 0 <= command <= 0xFF:
        raise ValueError("command out of range")
    data_length = len(data)
    if data_length > 255:
        raise ValueError("data exceeds 255 bytes")
    return bytes([START_BYTE, zone, command, data_length, *data, END_BYTE])


def parse_response(frame: bytes) -> ResponseFrame:
    """Parse one amplifier response ending with END_BYTE."""
    if len(frame) < 6:
        raise ArcamProtocolError("response too short")
    if frame[0] != START_BYTE:
        raise ArcamProtocolError("missing start byte")
    if frame[-1] != END_BYTE:
        raise ArcamProtocolError("missing end byte")
    zone = frame[1]
    command = frame[2]
    answer_code = frame[3]
    data_length = frame[4]
    expected = 5 + data_length + 1
    if len(frame) != expected:
        raise ArcamProtocolError(
            f"length mismatch: got {len(frame)} bytes, expected {expected}"
        )
    data = frame[5 : 5 + data_length]
    return ResponseFrame(
        zone=zone,
        command=command,
        answer_code=answer_code,
        data=data,
    )


def split_stream(buffer: bytearray) -> list[bytes]:
    """Split raw TCP bytes into complete frames (delimited by END_BYTE)."""
    out: list[bytes] = []
    start = 0
    while True:
        end_rel = buffer.find(END_BYTE, start)
        if end_rel < 0:
            break
        chunk = bytes(buffer[start : end_rel + 1])
        out.append(chunk)
        start = end_rel + 1
    del buffer[:start]
    return out
