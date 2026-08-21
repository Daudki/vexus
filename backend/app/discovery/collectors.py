"""
Discovery collectors.

`DiscoveryCollector` is a Protocol so the backend is swappable — Nmap
today, SNMP or agent-based collection later — without touching
DiscoveryService. `NmapCollector` defaults to `-sn` (host discovery /
ping scan only, no port scan) since that's the minimum needed for the
inventory use case; port/service discovery is an explicit opt-in via
`extra_args`, matching "make scan scope explicit."

`SimulatedCollector` exists for tests only. It is deliberately not
wired into the API — see discovery/router.py — because letting
synthetic hosts flow through the same path as real discovery would
require Asset-level is_synthetic tagging that doesn't exist yet.
"""
import shutil
import subprocess
import xml.etree.ElementTree as ET
from typing import Protocol

from app.assets.service import DiscoveredHost


class DiscoveryCollector(Protocol):
    def discover(self, target_ranges: list[str]) -> list[DiscoveredHost]: ...


class NmapCollector:
    """Wraps `nmap -oX -`. Requires nmap installed on the host running
    VEXUS. Only ever invoked after scope validation (see discovery/scope.py) —
    this class itself does not check authorization."""

    def __init__(self, extra_args: list[str] | None = None, timeout_seconds: int = 300):
        self.extra_args = extra_args or ["-sn"]
        self.timeout_seconds = timeout_seconds

    def discover(self, target_ranges: list[str]) -> list[DiscoveredHost]:
        if shutil.which("nmap") is None:
            raise RuntimeError(
                "nmap is not installed on this host. Install it (e.g. `apt install nmap`) "
                "or configure a different DiscoveryCollector."
            )

        cmd = ["nmap", "-oX", "-", *self.extra_args, *target_ranges]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self.timeout_seconds, check=True
        )
        return self._parse_xml(result.stdout)

    @staticmethod
    def _parse_xml(xml_text: str) -> list[DiscoveredHost]:
        hosts: list[DiscoveredHost] = []
        root = ET.fromstring(xml_text)

        for host_el in root.findall("host"):
            status_el = host_el.find("status")
            if status_el is None or status_el.get("state") != "up":
                continue

            ip_address = None
            mac_address = None
            vendor = None
            for addr in host_el.findall("address"):
                addrtype = addr.get("addrtype")
                if addrtype in ("ipv4", "ipv6"):
                    ip_address = addr.get("addr")
                elif addrtype == "mac":
                    mac_address = addr.get("addr")
                    vendor = addr.get("vendor")

            if not ip_address:
                continue  # can't inventory a host with no address

            hostname = None
            hostnames_el = host_el.find("hostnames")
            if hostnames_el is not None:
                name_el = hostnames_el.find("hostname")
                if name_el is not None:
                    hostname = name_el.get("name")

            operating_system = None
            os_el = host_el.find("os")
            if os_el is not None:
                match_el = os_el.find("osmatch")
                if match_el is not None:
                    operating_system = match_el.get("name")

            open_ports: list[int] = []
            ports_el = host_el.find("ports")
            if ports_el is not None:
                for port_el in ports_el.findall("port"):
                    state_el = port_el.find("state")
                    if state_el is not None and state_el.get("state") == "open":
                        port_id = port_el.get("portid")
                        if port_id is not None:
                            open_ports.append(int(port_id))

            hosts.append(
                DiscoveredHost(
                    ip_address=ip_address,
                    mac_address=mac_address,
                    hostname=hostname,
                    operating_system=operating_system,
                    vendor=vendor,
                    open_ports=open_ports,
                )
            )

        return hosts


class SimulatedCollector:
    """Test-only collector. Returns a fixed, caller-supplied host list
    instead of touching the network. Not reachable via the API."""

    def __init__(self, hosts: list[DiscoveredHost] | None = None):
        self._hosts = hosts or []

    def discover(self, target_ranges: list[str]) -> list[DiscoveredHost]:
        return list(self._hosts)
