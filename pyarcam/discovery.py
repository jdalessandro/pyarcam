"""Optional LAN discovery via the AMX DDDP-style banner (SH277E)."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from pyarcam.constants import DEFAULT_TCP_PORT


@dataclass(frozen=True)
class ArcamDiscoveredDevice:
    """Discovered unit on port 50000 (AMX banner and/or control protocol)."""

    host: str
    port: int
    model: str
    revision: str


def parse_amx_banner(data: bytes) -> tuple[str, str] | None:
    """Parse Device-Model and Device-Revision from an AMX discovery response."""
    try:
        text = data.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        return None
    if "AMXB" not in text:
        return None
    m_model = re.search(r"<Device-Model=([^>]+)>", text)
    m_rev = re.search(r"<Device-Revision=([^>]+)>", text)
    if not m_model or not m_rev:
        return None
    return m_model.group(1), m_rev.group(1)


def probe_amx(
    host: str,
    *,
    port: int = DEFAULT_TCP_PORT,
    timeout: float = 1.5,
) -> ArcamDiscoveredDevice | None:
    """Connect to *host* and send `AMX\\r`. If the unit responds like an Arcam SA10/SA20, return metadata.

    This uses the same AMX discovery string documented in SH277E (not the binary `!` frames).
    """
    try:
        with socket.create_connection((host, port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(b"AMX\r")
            buf = bytearray()
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    chunk = conn.recv(4096)
                except TimeoutError:
                    break
                except socket.timeout:
                    break
                if not chunk:
                    break
                buf.extend(chunk)
                if b"\r" in buf:
                    break
    except OSError:
        return None
    parsed = parse_amx_banner(bytes(buf))
    if parsed is None:
        return None
    model, revision = parsed
    return ArcamDiscoveredDevice(host=host, port=port, model=model, revision=revision)


def _probe_control_protocol(
    host: str,
    *,
    port: int = DEFAULT_TCP_PORT,
    timeout: float = 3.0,
) -> ArcamDiscoveredDevice | None:
    """Identify an SA10/SA20 by the binary SH277E protocol (``SYSTEM_MODEL`` / version).

    Used when the unit does not return an AMX discovery banner on port *port* but still
    accepts the control session (common in some power/network states).
    """
    from pyarcam.client import ArcamClient
    from pyarcam.exceptions import ArcamError

    try:
        with ArcamClient(host, port=port, timeout=timeout) as c:
            model = c.get_system_model().strip()
            if not model:
                return None
            try:
                major, minor = c.get_software_version()
                revision = f"{major}.{minor}"
            except ArcamError:
                revision = ""
    except (ArcamError, OSError):
        return None
    if not revision:
        revision = "?"
    return ArcamDiscoveredDevice(
        host=host, port=port, model=model, revision=revision
    )


def probe_lan_device(
    host: str,
    *,
    port: int = DEFAULT_TCP_PORT,
    amx_timeout: float = 0.5,
    control_timeout: float = 3.0,
    use_control_fallback: bool = True,
) -> ArcamDiscoveredDevice | None:
    """Try AMX discovery, then the IP control protocol, to find an Arcam on *host*.

    When *use_control_fallback* is true, a failed AMX response is followed by a
    short control session (``SYSTEM_MODEL``). That helps on DHCP when the banner
    probe is unreliable but TCP port 50000 still works.
    """
    dev = probe_amx(host, port=port, timeout=amx_timeout)
    if dev is not None:
        return dev
    if not use_control_fallback:
        return None
    return _probe_control_protocol(host, port=port, timeout=control_timeout)


def _ipv4_networks_from_ip_json(stdout: str) -> list[IPv4Network]:
    """Parse `ip -json addr` output into non-loopback global IPv4 prefixes."""
    out: list[IPv4Network] = []
    try:
        ifaces = json.loads(stdout)
    except json.JSONDecodeError:
        return out
    if not isinstance(ifaces, list):
        return out
    for iface in ifaces:
        if not isinstance(iface, dict):
            continue
        for addr in iface.get("addr_info", []):
            if not isinstance(addr, dict):
                continue
            if addr.get("family") != "inet":
                continue
            local = addr.get("local")
            plen = addr.get("prefixlen")
            if not local or plen is None:
                continue
            try:
                ip_obj = IPv4Address(local)
            except ValueError:
                continue
            if ip_obj.is_loopback or ip_obj.is_link_local:
                continue
            try:
                out.append(IPv4Network(f"{local}/{plen}", strict=False))
            except ValueError:
                continue
    return out


def _ipv4_networks_linux_iproute2() -> list[IPv4Network] | None:
    """Return subnets from iproute2 JSON, or None if unavailable."""
    try:
        completed = subprocess.run(
            ["ip", "-json", "addr", "show", "up", "scope", "global"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout:
        return None
    nets = _ipv4_networks_from_ip_json(completed.stdout)
    return nets if nets else None


def _ipv4_network_fallback_slash24() -> list[IPv4Network]:
    """Infer a single /24 from the interface used for the default IPv4 route.

    Uses the same UDP trick as many discovery examples; on multi-homed hosts this
    only sees one subnet, so prefer `local_ipv4_networks()` (Linux iproute2).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2.0)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        return []
    finally:
        s.close()
    parts = ip.split(".")
    if len(parts) != 4:
        return []
    try:
        return [IPv4Network(f"{parts[0]}.{parts[1]}.{parts[2]}.0/24", strict=False)]
    except ValueError:
        return []


def local_ipv4_networks() -> list[IPv4Network]:
    """Connected IPv4 subnets for this host (one entry per interface prefix).

    On Linux with ``ip`` from iproute2, all global IPv4 addresses are read and each
    prefix is returned (Wi‑Fi, Ethernet, bridges, etc.). Else falls back to inferring a
    single ``x.y.z.0/24`` from outbound routing.

    Link-local (169.254/16) and loopback are skipped. There is no portable way to list
    every interface on all operating systems without extra dependencies; non-Linux
    environments get the single-subnet heuristic only.
    """
    linux = _ipv4_networks_linux_iproute2()
    if linux:
        seen: set[str] = set()
        uniq: list[IPv4Network] = []
        for n in sorted(linux, key=lambda x: (int(x.network_address), x.prefixlen)):
            key = f"{n.network_address}/{n.prefixlen}"
            if key not in seen:
                seen.add(key)
                uniq.append(n)
        return uniq
    return _ipv4_network_fallback_slash24()


def scan_network(
    cidr: str,
    *,
    port: int = DEFAULT_TCP_PORT,
    timeout: float = 0.35,
    max_workers: int = 64,
    use_control_fallback: bool = True,
    control_timeout: float = 3.0,
) -> list[ArcamDiscoveredDevice]:
    """Probe each IPv4 host in *cidr* for an Arcam (parallel).

    Each host is tried with `probe_lan_device`: AMX discovery first, then (unless
    disabled) the binary control protocol so units that omit the AMX banner can still
    be found on DHCP.

    *timeout* applies to the AMX phase; *control_timeout* applies when the fallback
    runs. Refused connections stay fast; many subnets still benefit from a DHCP
    reservation or a narrow *cidr* to limit work.

    This performs a TCP scan on port *port* across the whole subnet; use a narrow CIDR
    when possible.
    """
    net = IPv4Network(cidr, strict=False)
    if net.prefixlen == 32:
        hosts = [str(net.network_address)]
    else:
        hosts = [str(ip) for ip in net.hosts()]
    results: list[ArcamDiscoveredDevice] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                probe_lan_device,
                h,
                port=port,
                amx_timeout=timeout,
                control_timeout=control_timeout,
                use_control_fallback=use_control_fallback,
            ): h
            for h in hosts
        }
        for fut in as_completed(futures):
            dev = fut.result()
            if dev is not None:
                results.append(dev)
    results.sort(key=lambda d: tuple(int(x) for x in d.host.split(".")))
    return results


def scan_local_networks(
    *,
    port: int = DEFAULT_TCP_PORT,
    timeout: float = 0.35,
    max_workers: int = 64,
    use_control_fallback: bool = True,
    control_timeout: float = 3.0,
) -> list[ArcamDiscoveredDevice]:
    """Discover Arcams on all local IPv4 subnets (`local_ipv4_networks`).

    Uses the same discovery strategy as `scan_network` (AMX, then optional control
    fallback). Hosts are deduplicated by IP. Large subnets scan slowly; prefer a
    narrow *cidr* with `scan_network` when you know the segment.

    For stable automation without hard-coding the amp’s IP, DHCP on the router/Pi plus
    ``scan_local_networks()`` is usually enough; a DHCP reservation by MAC is optional
    (still DHCP on the amp—only the lease is pinned server-side).
    """
    nets = local_ipv4_networks()
    seen_ip: set[str] = set()
    merged: list[ArcamDiscoveredDevice] = []
    for n in nets:
        for dev in scan_network(
            str(n),
            port=port,
            timeout=timeout,
            max_workers=max_workers,
            use_control_fallback=use_control_fallback,
            control_timeout=control_timeout,
        ):
            if dev.host not in seen_ip:
                seen_ip.add(dev.host)
                merged.append(dev)
    merged.sort(key=lambda d: tuple(int(x) for x in d.host.split(".")))
    return merged
