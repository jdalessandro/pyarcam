"""Command codes and enumerations for SA10/SA20 IP/serial protocol (SH277E)."""

from __future__ import annotations

from enum import IntEnum

# Transport
START_BYTE = 0x21
END_BYTE = 0x0D
DEFAULT_TCP_PORT = 50000
QUERY_BYTE = 0xF0

# Zone numbers (PDF)
ZONE_1 = 0x01
ZONE_2 = 0x02


class AnswerCode(IntEnum):
    """Response answer codes (Ac)."""

    STATUS_UPDATE = 0x00
    ZONE_INVALID = 0x82
    COMMAND_NOT_RECOGNISED = 0x83
    PARAMETER_NOT_RECOGNISED = 0x84
    COMMAND_INVALID_AT_THIS_TIME = 0x85
    INVALID_DATA_LENGTH = 0x86


class Command(IntEnum):
    """System command codes (Cc)."""

    POWER = 0x00
    DISPLAY_BRIGHTNESS = 0x01
    HEADPHONES = 0x02
    SOFTWARE_VERSION = 0x04
    FACTORY_RESET = 0x05
    SIMULATE_RC5 = 0x08
    VOLUME = 0x0D
    MUTE = 0x0E
    CURRENT_INPUT = 0x1D
    HEADPHONE_OVERRIDE = 0x1F
    HEARTBEAT = 0x25
    REBOOT = 0x26
    BALANCE = 0x3B
    INCOMING_SAMPLE_RATE = 0x44
    DC_OFFSET = 0x51
    SHORT_CIRCUIT = 0x52
    FRIENDLY_NAME = 0x53
    IP_ADDRESS = 0x54
    TIMEOUT_COUNTER = 0x55
    LIFTER_TEMPERATURE = 0x56
    OUTPUT_TEMPERATURE = 0x57
    AUTO_SHUTDOWN = 0x58
    INPUT_DETECT = 0x5A
    PROCESSOR_MODE_INPUT = 0x5B
    PROCESSOR_MODE_VOLUME = 0x5C
    SYSTEM_STATUS = 0x5D
    SYSTEM_MODEL = 0x5E
    DAC_FILTER = 0x61


class PowerState(IntEnum):
    STANDBY = 0x00
    ON = 0x01


class DisplayBrightness(IntEnum):
    OFF = 0x00
    DIM = 0x01
    FULL = 0x02


class InputSource(IntEnum):
    PHONO = 0x01
    AUX = 0x02
    PVR = 0x03
    AV = 0x04
    STB = 0x05
    CD = 0x06
    BD = 0x07
    SAT = 0x08


class SampleRateCode(IntEnum):
    SR_32K = 0x00
    SR_44_1K = 0x01
    SR_48K = 0x02
    SR_88_2K = 0x03
    SR_96K = 0x04
    SR_176_4K = 0x05
    SR_192K = 0x06
    UNKNOWN = 0x07
    UNDETECTED = 0x08


class DacFilter(IntEnum):
    LINEAR_PHASE_FAST_ROLL_OFF = 0x00
    LINEAR_PHASE_SLOW_ROLL_OFF = 0x01
    MINIMUM_PHASE_FAST_ROLL_OFF = 0x02
    MINIMUM_PHASE_SLOW_ROLL_OFF = 0x03
    BRICK_WALL = 0x04
    CORRECTED_PHASE_FAST_ROLL_OFF = 0x05
    APODIZING = 0x06


class AutoShutdown(IntEnum):
    DISABLED = 0x00
    MINUTES_30 = 0x01
    HOURS_1 = 0x02
    HOURS_2 = 0x03
    HOURS_4 = 0x04


# RC5 system code used by SA10/SA20 basic IR simulation (PDF table)
RC5_SYSTEM = 0x10


class RC5Command(IntEnum):
    """RC5 command bytes paired with RC5_SYSTEM for simulate_rc5 (PDF)."""

    STANDBY = 0x0C
    DISP = 0x3B
    MUTE = 0x0D
    VOL_UP = 0x10
    VOL_DOWN = 0x11
    BALANCE_LEFT = 0x26
    BALANCE_RIGHT = 0x28
    PHONO = 0x75
    CD = 0x76
    BD = 0x62
    SAT = 0x1B
    PVR = 0x60
    AV = 0x5E
    AUX = 0x63
    STB = 0x64
    POWER_ON = 0x7B
    POWER_OFF = 0x7C
    MUTE_ON = 0x1A
    MUTE_OFF = 0x78
    DISPLAY_OFF = 0x1F
    DISPLAY_L1 = 0x22
    DISPLAY_L2 = 0x23
    BACK = 0x33
    HOME = 0x2B
    MENU = 0x52
    NAV_UP = 0x56
    NAV_LEFT = 0x51
    OK = 0x57
    NAV_RIGHT = 0x50
    NAV_DOWN = 0x55
