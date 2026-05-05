# pyarcam

**pyarcam** is a small, typed Python library for controlling **Arcam SA10** and **SA20** integrated amplifiers over the network. It implements the same **RS232/NET binary protocol** Arcam documents for IP control (sometimes referenced in documentation as **SH277E**), using **TCP port 50000** on the amplifier’s LAN address.

This project is **not affiliated with or endorsed by Arcam**. Product names are trademarks of their owners.

---

## Table of contents

- [Why this exists](#why-this-exists)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Network setup](#network-setup)
- [Quick start](#quick-start)
- [Discovery and DHCP](#discovery-and-dhcp)
- [Usage patterns](#usage-patterns)
- [API overview](#api-overview)
- [Errors](#errors)
- [How the code fits together](#how-the-code-fits-together)
- [Development](#development)
- [License](#license)

---

## Why this exists

Arcam exposes **structured commands** (power, volume, input, mute, diagnostics, etc.) over Ethernet. pyarcam wraps those commands in a normal Python API so you can automate or integrate the amplifier without raw sockets and manual framing—while still allowing low-level access when you need it.

---

## Features

- **`ArcamClient`** — connect to `host:50000`, send commands, interpret typed responses.
- **Discovery helpers** — locate amplifiers on the LAN using **AMX-style discovery** on port 50000 and, if needed, the **same binary control session** used for normal operation (useful when discovery banners are unreliable).
- **Multi-subnet Linux discovery** — enumerate **all connected IPv4 subnets** via `ip -json` (e.g. Wi‑Fi + Ethernet on a Raspberry Pi) instead of only inferring one subnet from the default route.
- **Low-level escape hatch** — `raw_command` plus `pack_command` / `parse_response` for anything not wrapped yet.
- **`py.typed`** — type annotations for editors and type checkers.

---

## Requirements

- **Python** 3.10 or newer.
- **Amplifier** reachable at an IPv4 address on your LAN (DHCP or static).
- **TCP port 50000** reachable from the machine running Python (no firewall drop between client and amp).
- Optional **Linux `ip` binary** (iproute2) for best multi-interface subnet detection (`local_ipv4_networks`).

---

## Installation

### From a cloned repository

```bash
git clone <your-fork-or-upstream-url>
cd pyarcam
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### Without installing (for scripts on constrained devices)

Point **`PYTHONPATH`** at the repository root so `import pyarcam` resolves:

```bash
export PYTHONPATH=/path/to/pyarcam
python3 your_script.py
```

---

## Network setup

1. **Same broadcast domain as the amp**  
   The controlling machine must be able to open a **TCP connection** to `<amplifier-ip>:50000`. Routing across VLANs is fine if your firewall allows it; NAT hairpin from “outside” generally is not.

2. **Amplifier IP control**  
   Ensure the SA10/SA20 is configured for **Ethernet / IP control** per Arcam’s documentation (DHCP or fixed IP on the amp—either works with pyarcam).

3. **Standby behavior**  
   Some units may not accept connections when fully powered down or when certain standby/network modes apply. If commands fail, confirm whether **network standby / IP control while off** is enabled on the device for your use case.

4. **Firewalls**  
   Allow **outbound TCP to port 50000** on the client, **inbound** on the amplifier side if you filter traffic.

---

## Quick start

```python
from pyarcam import ArcamClient, InputSource

AMP_IP = "192.168.1.50"  # replace with your amp’s address

with ArcamClient(AMP_IP, timeout=5.0) as amp:
    amp.power_on()
    print(amp.get_power_state())
    print(amp.get_volume())
    amp.set_input(InputSource.CD)
    amp.set_volume(35)
```

---

## Discovery and DHCP

You do **not** have to set a static IP on the amplifier. Typical approaches:

| Approach | When to use |
|----------|-------------|
| **Run discovery** from a host on the same networks as the amp | You are fine scanning occasionally or on startup. |
| **DHCP reservation** (by MAC) on your router or Pi | You want a **stable** address for scripts or Home Assistant without editing the amp’s network menu. |
| **Narrow CIDR** with `scan_network("192.168.100.0/24")` | You know the segment (e.g. downlink from a Pi) and want a **faster** scan than all interfaces. |

### Scan all local IPv4 subnets (Linux-friendly)

```python
from pyarcam import scan_local_networks, ArcamClient

devices = scan_local_networks()
if not devices:
    raise SystemExit("No Arcam found on any local subnet")

host = devices[0].host
print(f"Found {devices[0].model!r} at {host}")

with ArcamClient(host, timeout=5.0) as amp:
    print(amp.get_system_model(), amp.get_software_version())
```

### Scan a specific range

```python
from pyarcam import scan_network

found = scan_network("192.168.100.0/24", timeout=0.35, control_timeout=3.0)
```

**How discovery works (short):**

1. **`probe_lan_device(ip)`** — tries **AMX** text discovery on port 50000, then (by default) a short **control-protocol** check (`SYSTEM_MODEL` / version) if the AMX banner is missing.
2. **`local_ipv4_networks()`** — on Linux, uses `ip -json addr show up scope global` to list **all** non-loopback, non–link-local IPv4 prefixes. Else falls back to a single inferred `/24` from the default route.
3. **`scan_local_networks()`** — runs a port scan + discovery per host on each local subnet, deduplicated by IP.

**Note:** Full-subnet scans open many TCP connections. Prefer a **reservation** or a **known CIDR** in production, and tune `timeout`, `control_timeout`, and `max_workers` if needed.

---

## Usage patterns

### Context manager (recommended)

```python
with ArcamClient("192.168.100.10") as amp:
    amp.unmute()
```

### Explicit connect / close

```python
amp = ArcamClient("192.168.100.10")
try:
    amp.connect()
    amp.heartbeat()
finally:
    amp.close()
```

### Zone 2

```python
from pyarcam import ArcamClient, ZONE_2

with ArcamClient("192.168.100.10", zone=ZONE_2) as amp:
    amp.get_volume()
```

### IR simulation (RC5)

```python
from pyarcam import ArcamClient, RC5Command

with ArcamClient("192.168.100.10") as amp:
    amp.simulate_rc5_system(int(RC5Command.VOL_UP))
```

### Raw protocol access

```python
from pyarcam import ArcamClient, Command, QUERY_BYTE, pack_command

with ArcamClient("192.168.100.10") as amp:
    r = amp.raw_command(Command.SOFTWARE_VERSION, bytes([QUERY_BYTE]))
    print(r.data)
```

---

## API overview

### `ArcamClient` (selected methods)

| Area | Methods |
|------|---------|
| Power | `power_on`, `power_off`, `power_toggle`, `get_power_state` |
| Volume / mute | `set_volume`, `volume_up`, `volume_down`, `get_volume`, `mute`, `unmute`, `mute_toggle`, `get_mute` |
| Input | `set_input`, `get_input` |
| Display | `set_display_brightness`, `get_display_brightness` |
| Headphones | `get_headphones_connected`, `set_headphone_override_clear`, `set_headphone_override_set`, `get_headphone_override` |
| Info / network on amp | `get_software_version`, `get_system_model`, `get_friendly_name`, `set_friendly_name`, `get_ip_address`, `set_ip_address`, `set_dhcp` |
| Diagnostics / extras | `get_incoming_sample_rate`, `get_dc_offset`, `get_short_circuit`, `get_lifter_temperature_c`, `get_output_temperature_c`, `get_input_present`, `get_timeout_minutes` |
| System | `request_system_status`, `heartbeat`, `reboot`, `factory_reset` |
| RC5 | `simulate_rc5`, `simulate_rc5_system` |
| Balance / DAC / auto-off / processor | `set_balance`, `get_balance`, `balance_nudge_left`, `balance_nudge_right`, `set_dac_filter`, `get_dac_filter`, `set_auto_shutdown`, `get_auto_shutdown`, `set_processor_mode_input`, `get_processor_mode_input`, `set_processor_mode_volume`, `get_processor_mode_volume` |
| Core | `raw_command`, `connect`, `close` |

For the full set, see `pyarcam/client.py` and the `Command` enum in `pyarcam/constants.py`.

### Discovery and framing (exports)

| Symbol | Role |
|--------|------|
| `scan_local_networks` | Scan every local IPv4 subnet for Arcams |
| `scan_network` | Scan one CIDR (e.g. `192.168.0.0/24`) |
| `probe_lan_device` | Test a single IP (AMX + optional control fallback) |
| `probe_amx` | AMX-only probe |
| `local_ipv4_networks` | List `IPv4Network` entries for this host |
| `ArcamDiscoveredDevice` | `host`, `port`, `model`, `revision` |
| `pack_command` / `parse_response` / `ResponseFrame` | Build and parse binary frames |

### Exceptions

- `ArcamError` — base
- `ArcamTimeoutError` — no matching response in time
- `ArcamCommandError` — amplifier returned an error answer code (Ac ≥ 0x80)
- `ArcamProtocolError` — malformed or unexpected frame or data

---

## Errors

- Increase **`timeout=`** on `ArcamClient` if the network is slow or the unit is busy.
- If the amp returns **command not recognised** or **invalid at this time**, the model/firmware or input mode may not support that command (see Arcam’s protocol documentation for your series).
- Use **`raw_command`** only with bytes you have validated; wrong payloads can trigger factory reset or other destructive operations (e.g. `factory_reset` is exposed in the client—use with care).

---

## How the code fits together

- **`framing.py`** — `pack_command` / `parse_response` / `split_stream` for the `!…\r` style binary framing.
- **`client.py`** — one TCP connection, thread lock, send command, read until a response matches the same **command code** and **zone**.
- **`constants.py`** — command bytes (`Command`), answer codes, enums (`InputSource`, `PowerState`, …), RC5 helpers.
- **`codec.py`** — encode/decode the current-input byte for command `0x1D`.
- **`discovery.py`** — subnet enumeration (Linux `ip -json`), parallel probes, AMX + optional control identification.

---

## Development

Editable install with optional dev dependencies (pytest):

```bash
pip install -e ".[dev]"
pytest
```
---

## License

MIT — see the [`pyproject.toml`](pyproject.toml) metadata.
