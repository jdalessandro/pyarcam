"""TCP client for Arcam SA10/SA20 network (port 50000) control."""

from __future__ import annotations

import ipaddress
import re
import socket
import threading
import time
from types import TracebackType
from typing import Type

from pyarcam.codec import decode_current_input_byte, encode_current_input_byte
from pyarcam.constants import (
    AutoShutdown,
    Command,
    DacFilter,
    DEFAULT_TCP_PORT,
    DisplayBrightness,
    InputSource,
    PowerState,
    QUERY_BYTE,
    RC5_SYSTEM,
    SampleRateCode,
    ZONE_1,
)
from pyarcam.exceptions import ArcamCommandError, ArcamProtocolError, ArcamTimeoutError
from pyarcam.framing import ResponseFrame, pack_command, parse_response, split_stream

_ERROR_THRESHOLD = 0x80


class ArcamClient:
    """Callable wrapper around the RS232/NET binary protocol (SH277E).

    IP control uses TCP port 50000. Methods raise ArcamCommandError when the
    amplifier returns Ac ≥ 0x80 (see AnswerCode).
    """

    def __init__(
        self,
        host: str,
        *,
        port: int = DEFAULT_TCP_PORT,
        zone: int = ZONE_1,
        timeout: float = 3.0,
    ) -> None:
        self._host = host
        self._port = port
        self._zone = zone
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._rx_buffer = bytearray()
        self._lock = threading.Lock()

    def _ensure_connected(self) -> None:
        if self._sock is not None:
            return
        s = socket.create_connection((self._host, self._port), timeout=self._timeout)
        s.settimeout(self._timeout)
        self._sock = s

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def zone(self) -> int:
        return self._zone

    def connect(self) -> None:
        """Open the TCP connection."""
        with self._lock:
            self._ensure_connected()

    def close(self) -> None:
        """Close the TCP connection."""
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                finally:
                    self._sock = None
                    self._rx_buffer.clear()

    def __enter__(self) -> ArcamClient:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def raw_command(self, command: int | Command, data: bytes) -> ResponseFrame:
        """Send a raw command and wait for the matching response."""
        cc = int(command)
        payload = pack_command(self._zone, cc, data)
        with self._lock:
            self._ensure_connected()
            assert self._sock is not None
            self._sock.sendall(payload)
            return self._read_matching(cc)

    # --- Power (0x00) ---

    def power_off(self) -> None:
        self._simple(Command.POWER, bytes([0x00]))

    def power_on(self) -> None:
        self._simple(Command.POWER, bytes([0x01]))

    def power_toggle(self) -> None:
        self._simple(Command.POWER, bytes([0x02]))

    def get_power_state(self) -> PowerState:
        r = self._simple(Command.POWER, bytes([QUERY_BYTE]))
        return PowerState(r.data[0])

    # --- Display (0x01) ---

    def set_display_brightness(self, level: DisplayBrightness) -> None:
        self._simple(Command.DISPLAY_BRIGHTNESS, bytes([int(level)]))

    def get_display_brightness(self) -> DisplayBrightness:
        r = self._simple(Command.DISPLAY_BRIGHTNESS, bytes([QUERY_BYTE]))
        return DisplayBrightness(r.data[0])

    # --- Headphones (0x02) ---

    def get_headphones_connected(self) -> bool:
        r = self._simple(Command.HEADPHONES, bytes([QUERY_BYTE]))
        return r.data[0] == 0x01

    # --- Software (0x04) ---

    def get_software_version(self) -> tuple[int, int]:
        r = self._simple(Command.SOFTWARE_VERSION, bytes([QUERY_BYTE]))
        if len(r.data) < 2:
            raise ArcamProtocolError("short software version")
        return r.data[0], r.data[1]

    # --- Factory reset (0x05) ---

    def factory_reset(self) -> None:
        self._simple(Command.FACTORY_RESET, bytes([0xAA, 0xAA]))

    # --- RC5 (0x08) ---

    def simulate_rc5(self, system: int, command: int) -> None:
        self._simple(Command.SIMULATE_RC5, bytes([system & 0xFF, command & 0xFF]))

    def simulate_rc5_system(self, command: int) -> None:
        """Convenience: use the fixed SA10/SA20 RC5 system code (0x10)."""
        self.simulate_rc5(RC5_SYSTEM, command)

    # --- Volume (0x0D) ---

    def set_volume(self, level: int) -> int:
        if not 0 <= level <= 99:
            raise ValueError("volume must be 0..99")
        r = self._simple(Command.VOLUME, bytes([level]))
        return r.data[0] if r.data else level

    def volume_up(self) -> int:
        r = self._simple(Command.VOLUME, bytes([0xF1]))
        return r.data[0]

    def volume_down(self) -> int:
        r = self._simple(Command.VOLUME, bytes([0xF2]))
        return r.data[0]

    def get_volume(self) -> int:
        r = self._simple(Command.VOLUME, bytes([QUERY_BYTE]))
        return r.data[0]

    # --- Mute (0x0E) ---

    def mute(self) -> None:
        self._simple(Command.MUTE, bytes([0x00]))

    def unmute(self) -> None:
        self._simple(Command.MUTE, bytes([0x01]))

    def mute_toggle(self) -> None:
        self._simple(Command.MUTE, bytes([0x02]))

    def get_mute(self) -> bool:
        r = self._simple(Command.MUTE, bytes([QUERY_BYTE]))
        return r.data[0] == 0x00

    # --- Input (0x1D) ---

    def set_input(self, source: InputSource, *, processor_mode: bool = False) -> None:
        b = encode_current_input_byte(source, processor_mode)
        self._simple(Command.CURRENT_INPUT, bytes([b]))

    def get_input(self) -> tuple[InputSource | None, bool]:
        r = self._simple(Command.CURRENT_INPUT, bytes([QUERY_BYTE]))
        if not r.data:
            raise ArcamProtocolError("empty input response")
        return decode_current_input_byte(r.data[0])

    # --- Headphone override (0x1F) ---

    def set_headphone_override_clear(self) -> None:
        self._simple(Command.HEADPHONE_OVERRIDE, bytes([0x00]))

    def set_headphone_override_set(self) -> None:
        self._simple(Command.HEADPHONE_OVERRIDE, bytes([0x01]))

    def get_headphone_override(self) -> int:
        r = self._simple(Command.HEADPHONE_OVERRIDE, bytes([QUERY_BYTE]))
        return r.data[0]

    # --- Heartbeat (0x25) ---

    def heartbeat(self) -> None:
        self._simple(Command.HEARTBEAT, bytes([QUERY_BYTE]))

    # --- Reboot (0x26) ---

    def reboot(self) -> None:
        self._simple(Command.REBOOT, b"REBOOT")

    # --- Balance (0x3B) ---

    def set_balance(self, data_byte: int) -> int:
        r = self._simple(Command.BALANCE, bytes([data_byte & 0xFF]))
        return r.data[0]

    def get_balance(self) -> int:
        r = self._simple(Command.BALANCE, bytes([QUERY_BYTE]))
        return r.data[0]

    def balance_nudge_right(self) -> int:
        r = self._simple(Command.BALANCE, bytes([0xF1]))
        return r.data[0]

    def balance_nudge_left(self) -> int:
        r = self._simple(Command.BALANCE, bytes([0xF2]))
        return r.data[0]

    # --- Sample rate (0x44) ---

    def get_incoming_sample_rate(self) -> SampleRateCode:
        r = self._simple(Command.INCOMING_SAMPLE_RATE, bytes([QUERY_BYTE]))
        return SampleRateCode(r.data[0])

    # --- DC offset (0x51) ---

    def get_dc_offset(self) -> bool:
        r = self._simple(Command.DC_OFFSET, bytes([QUERY_BYTE]))
        return r.data[0] == 0x01

    # --- Short circuit (0x52) SA20 only ---

    def get_short_circuit(self) -> bool:
        r = self._simple(Command.SHORT_CIRCUIT, bytes([QUERY_BYTE]))
        return r.data[0] == 0x01

    # --- Friendly name (0x53) ---

    def get_friendly_name(self) -> str:
        r = self._simple(Command.FRIENDLY_NAME, bytes([QUERY_BYTE]))
        return r.data.decode("ascii", errors="replace").rstrip()

    def set_friendly_name(self, name: str) -> str:
        upper = name.upper()
        if not re.fullmatch(r"[A-Z0-9 ]+", upper):
            raise ValueError("only A-Z, 0-9 and space allowed")
        raw = upper.encode("ascii")
        if len(raw) > 10:
            raise ValueError("friendly name max length is 10 characters")
        r = self._simple(Command.FRIENDLY_NAME, raw)
        return r.data.decode("ascii", errors="replace").rstrip()

    # --- IP address (0x54) ---

    def get_ip_address(self) -> ipaddress.IPv4Address:
        r = self._simple(Command.IP_ADDRESS, bytes([QUERY_BYTE]))
        if len(r.data) != 4:
            raise ArcamProtocolError("expected 4 byte IP from amplifier")
        return ipaddress.IPv4Address(r.data)

    def set_ip_address(self, address: ipaddress.IPv4Address) -> ipaddress.IPv4Address:
        r = self._simple(Command.IP_ADDRESS, address.packed)
        if len(r.data) != 4:
            raise ArcamProtocolError("expected 4 byte IP in response")
        return ipaddress.IPv4Address(r.data)

    def set_dhcp(self) -> ipaddress.IPv4Address:
        """Set all IP octets to 0 to enable DHCP (per SH277E)."""
        return self.set_ip_address(ipaddress.IPv4Address("0.0.0.0"))

    # --- Timeout counter (0x55) ---

    def get_timeout_minutes(self) -> int:
        r = self._simple(Command.TIMEOUT_COUNTER, bytes([QUERY_BYTE]))
        if len(r.data) < 2:
            raise ArcamProtocolError("short timeout response")
        return (r.data[0] << 8) | r.data[1]

    # --- Temperatures ---

    def get_lifter_temperature_c(self) -> int:
        r = self._simple(Command.LIFTER_TEMPERATURE, bytes([QUERY_BYTE]))
        return r.data[0]

    def get_output_temperature_c(self) -> int:
        r = self._simple(Command.OUTPUT_TEMPERATURE, bytes([QUERY_BYTE]))
        return r.data[0]

    # --- Auto shutdown (0x58) ---

    def set_auto_shutdown(self, mode: AutoShutdown) -> AutoShutdown:
        r = self._simple(Command.AUTO_SHUTDOWN, bytes([int(mode)]))
        return AutoShutdown(r.data[0])

    def get_auto_shutdown(self) -> AutoShutdown:
        r = self._simple(Command.AUTO_SHUTDOWN, bytes([QUERY_BYTE]))
        return AutoShutdown(r.data[0])

    # --- Input detect (0x5A) ---

    def get_input_present(self) -> bool:
        r = self._simple(Command.INPUT_DETECT, bytes([QUERY_BYTE]))
        return r.data[0] == 0x01

    # --- Processor mode (0x5B / 0x5C) ---

    def set_processor_mode_input(self, value: int) -> None:
        self._simple(Command.PROCESSOR_MODE_INPUT, bytes([value & 0xFF]))

    def get_processor_mode_input(self) -> int:
        r = self._simple(Command.PROCESSOR_MODE_INPUT, bytes([QUERY_BYTE]))
        return r.data[0]

    def set_processor_mode_volume(self, level: int) -> int:
        if not 0 <= level <= 99:
            raise ValueError("processor volume must be 0..99")
        r = self._simple(Command.PROCESSOR_MODE_VOLUME, bytes([level]))
        return r.data[0]

    def get_processor_mode_volume(self) -> int:
        r = self._simple(Command.PROCESSOR_MODE_VOLUME, bytes([QUERY_BYTE]))
        return r.data[0]

    # --- System status / model ---

    def request_system_status(self) -> None:
        """Ask the unit to emit current status (may produce multiple follow-up frames)."""
        self._simple(Command.SYSTEM_STATUS, bytes([QUERY_BYTE]))

    def get_system_model(self) -> str:
        r = self._simple(Command.SYSTEM_MODEL, bytes([QUERY_BYTE]))
        return r.data.decode("ascii", errors="replace")

    # --- DAC filter (0x61) ---

    def set_dac_filter(self, filt: DacFilter) -> DacFilter:
        r = self._simple(Command.DAC_FILTER, bytes([int(filt)]))
        return DacFilter(r.data[0])

    def get_dac_filter(self) -> DacFilter:
        r = self._simple(Command.DAC_FILTER, bytes([QUERY_BYTE]))
        return DacFilter(r.data[0])

    # --- Internals ---

    def _simple(self, command: Command, data: bytes) -> ResponseFrame:
        r = self.raw_command(command, data)
        self._maybe_raise_error(r)
        return r

    def _maybe_raise_error(self, frame: ResponseFrame) -> None:
        if frame.answer_code >= _ERROR_THRESHOLD:
            raise ArcamCommandError(
                f"amplifier error answer code 0x{frame.answer_code:02X}",
                answer_code=frame.answer_code,
                zone=frame.zone,
                command=frame.command,
            )

    def _read_matching(self, command_code: int) -> ResponseFrame:
        deadline = time.monotonic() + self._timeout
        assert self._sock is not None
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._sock.settimeout(min(remaining, 0.25))
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                raise ArcamProtocolError("connection closed by amplifier")
            self._rx_buffer.extend(chunk)
            frames_raw = split_stream(self._rx_buffer)
            for raw in frames_raw:
                # Ignore ASCII AMX discovery noise if mixed into buffer
                if raw.startswith(b"AMXB"):
                    continue
                try:
                    frame = parse_response(raw)
                except ArcamProtocolError:
                    continue
                if frame.zone != self._zone:
                    continue
                if frame.command != command_code:
                    continue
                return frame
        raise ArcamTimeoutError(
            f"no response for command 0x{command_code:02X} within {self._timeout}s"
        )
