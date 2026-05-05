"""Python client library for Arcam SA10/SA20 IP control (SH277E RS232/NET protocol)."""

from pyarcam.client import ArcamClient
from pyarcam.codec import decode_current_input_byte, encode_current_input_byte
from pyarcam.constants import (
    AnswerCode,
    AutoShutdown,
    Command,
    DacFilter,
    DEFAULT_TCP_PORT,
    DisplayBrightness,
    InputSource,
    PowerState,
    QUERY_BYTE,
    RC5_SYSTEM,
    RC5Command,
    SampleRateCode,
    ZONE_1,
    ZONE_2,
)
from pyarcam.discovery import (
    ArcamDiscoveredDevice,
    local_ipv4_networks,
    parse_amx_banner,
    probe_amx,
    probe_lan_device,
    scan_local_networks,
    scan_network,
)
from pyarcam.exceptions import ArcamCommandError, ArcamError, ArcamProtocolError, ArcamTimeoutError
from pyarcam.framing import ResponseFrame, pack_command, parse_response

__all__ = [
    "AnswerCode",
    "ArcamClient",
    "ArcamCommandError",
    "ArcamDiscoveredDevice",
    "ArcamError",
    "ArcamProtocolError",
    "ArcamTimeoutError",
    "AutoShutdown",
    "Command",
    "DacFilter",
    "DEFAULT_TCP_PORT",
    "DisplayBrightness",
    "InputSource",
    "PowerState",
    "QUERY_BYTE",
    "RC5_SYSTEM",
    "RC5Command",
    "ResponseFrame",
    "SampleRateCode",
    "ZONE_1",
    "ZONE_2",
    "decode_current_input_byte",
    "encode_current_input_byte",
    "pack_command",
    "parse_amx_banner",
    "parse_response",
    "local_ipv4_networks",
    "probe_amx",
    "probe_lan_device",
    "scan_local_networks",
    "scan_network",
]
