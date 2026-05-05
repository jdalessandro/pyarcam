"""Encode/decode helpers for SA10/SA20 protocol fields."""

from __future__ import annotations

from pyarcam.constants import InputSource


def decode_current_input_byte(value: int) -> tuple[InputSource | None, bool]:
    """Decode 0x1D input byte (normal vs processor mode nibble)."""
    low = value & 0x0F
    hi_nibble = (value >> 4) & 0x0F
    processor_mode = hi_nibble == 0x01
    try:
        src = InputSource(low)
    except ValueError:
        src = None
    return src, processor_mode


def encode_current_input_byte(source: InputSource, processor_mode: bool = False) -> int:
    """Encode input selection for 0x1D."""
    high = 0x10 if processor_mode else 0x00
    return high | (source.value & 0x0F)
