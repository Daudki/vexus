"""
Discovery collectors.

`DiscoveryCollector` is a Protocol so the backend is swappable — Nmap or
the dependency-free Python TCP fallback today, SNMP or agent-based collection later — without touching
DiscoveryService.

`NmapCollector` builds its `nmap` command from a `ScanProfile` rather than
a free-form `extra_args` list. The previous default (`-sn`, host-discovery
/ ping scan only — no port scan at all) is preserved as the explicit
`HOST_DISCOVERY` profile, but is no longer the default: the default is
now `STEALTH_SYN` (`-sS -T3 -PE -PS21,22,80,443,3389 -PA80,443`), a TCP
SYN "half-open" scan that completes the TCP handshake only far enough to
detect an open port and never sends an ACK back. Compared to `-sT`
(connect scan) it leaves no completed connection in the target's socket
table; compared to `-sn` it actually enumerates open ports and (when
`-sV`/`-O` is selected via `SERVICE_VERSION`/`OS_DETECT`) service banners
and OS fingerprints. The "stealth" framing is the conventional industry
term for `-sS`; it is not a guarantee of unobservability — any scan of
an unauthorized range is still refused before this class is ever invoked
(see app/discovery/scope.py), and an IDS-aware target can still see the
probes.

Profiles are a closed enum (`ScanProfile`), not a free-form string. The
operator's intent is made explicit at the API boundary
(`POST /discovery/scans { profile: "stealth_syn" }`) instead of being
implicit in a shell-escaped argument list. Adding a new profile is a
deliberate code change in this file — exactly the discipline the spec
demands of "make scan scope explicit."

`SimulatedCollector` exists for tests only. It is deliberately not
wired into the API — see discovery/router.py — because letting
synthetic hosts flow through the same path as real discovery would
require Asset-level is_synthetic tagging that doesn't exist yet.
"""
import concurrent.futures
import enum
import shutil
import socket
import subprocess
import xml.etree.ElementTree as ET
from typing import Protocol

from app.assets.service import DiscoveredHost


class ScanProfile(str, enum.Enum):
    """Closed enum of supported nmap scan profiles.

    Adding a new profile is a code change here, not a runtime parameter —
    this is the "make scan scope explicit" rule from the spec, applied to
    the scan technique itself, not just the target range.
    """

    # `-sn`: ping scan only. Fast host discovery without any port scan.
    # Cheapest profile, useful for "is anything alive on this network?"
    # but reports no services/ports. Kept for backwards compatibility
    # with the old default.
    HOST_DISCOVERY = "host_discovery"

    # `-sS` (default): TCP SYN "stealth" scan. Half-opens the TCP
    # handshake (sends SYN, reads SYN/ACK or RST, never ACKs back) so
    # no completed connection is logged in the target's application-level
    # socket table. Combined with `-T3` (normal timing) and standard
    # host-discovery probes (ICMP echo + TCP SYN/ACK pings on a handful
    # of common ports). This is the "stealth scan" the spec calls for.
    STEALTH_SYN = "stealth_syn"

    # `-sS -sV`: stealth SYN scan plus service version detection. nmap
    # probes each open port with banner-grabbing signatures and reports
    # `service_name` / `service_product` / `service_version`. Slower
    # than `STEALTH_SYN` (each open port gets an extra round of probes)
    # but produces the data the Asset Intelligence change detector keys
    # off (port + service fingerprint changes).
    SERVICE_VERSION = "service_version"

    # `-sS -O`: stealth SYN scan plus OS fingerprinting via TCP/IP stack
    # signatures. Requires root/raw sockets on most platforms; nmap will
    # silently skip OS detection if privileges are insufficient and the
    # resulting DiscoveredHost simply won't carry an OS field. Doesn't
    # run service version detection — pair with `SERVICE_VERSION` via
    # the `FULL` profile if both are wanted.
    OS_DETECT = "os_detect"

    # `-sS -sV -O`: stealth SYN scan + service version + OS detection.
    # Slowest and noisiest profile. Use when you have a maintenance
    # window and want the most complete inventory baseline.
    FULL = "full"


# Ordered, deterministic nmap flag templates per profile. Each profile's
# flags are assembled exactly once here; nothing downstream gets to
# inject free-form args into the subprocess call (the `extra_args`
# constructor parameter is retained for backwards compatibility with
# existing callers/tests but is no longer the primary API — `profile`
# is).
#
# Notes on the chosen flags:
#   - `-sS`          TCP SYN scan (the "stealth" technique)
#   - `-sn`          ping scan only (no port scan) — host_discovery profile
#   - `-sV`          service version detection (banner grabbing)
#   - `-O`           OS detection via TCP/IP stack fingerprinting
#   - `-PE`          ICMP echo probe (host discovery)
#   - `-PS<ports>`   TCP SYN ping probe (host discovery, doesn't count as a port scan)
#   - `-PA<ports>`   TCP ACK ping probe (host discovery)
#   - `-T1..5`       timing template: 0=paranoid, 1=sneaky, 2=polite,
#                    3=normal (default), 4=aggressive, 5=insane
#   - `--max-retries=2` cap retries so a flaky host doesn't stall the scan
#   - `--host-timeout=2m` per-host ceiling so one slow host can't stall the whole scan
_PROFILE_FLAGS: dict[ScanProfile, list[str]] = {
    ScanProfile.HOST_DISCOVERY: [
        "-sn",
        "-PE",
        "-PS21,22,80,443,3389",
        "-PA80,443",
        "--max-retries=2",
        "--host-timeout=2m",
    ],
    ScanProfile.STEALTH_SYN: [
        "-sS",
        "-T3",
        "-PE",
        "-PS21,22,80,443,3389",
        "-PA80,443",
        "--max-retries=2",
        "--host-timeout=2m",
    ],
    ScanProfile.SERVICE_VERSION: [
        "-sS",
        "-sV",
        "-T3",
        "-PE",
        "-PS21,22,80,443,3389",
        "-PA80,443",
        "--max-retries=2",
        "--host-timeout=5m",
        "--version-intensity=5",
    ],
    ScanProfile.OS_DETECT: [
        "-sS",
        "-O",
        "-T3",
        "-PE",
        "-PS21,22,80,443,3389",
        "-PA80,443",
        "--max-retries=2",
        "--host-timeout=5m",
        "--osscan-limit",
    ],
    ScanProfile.FULL: [
        "-sS",
        "-sV",
        "-O",
        "-T3",
        "-PE",
        "-PS21,22,80,443,3389",
        "-PA80,443",
        "--max-retries=2",
        "--host-timeout=10m",
        "--version-intensity=5",
        "--osscan-limit",
    ],
}


# Default timing template (`-T` flag) used when no profile is specified.
# `-T3` is nmap's own default and the right tradeoff for an authorized
# internal scan — fast enough to finish a /24 in minutes, slow enough to
# avoid saturating a slow WAN link or tripping low-threshold IDS rules.
# Operators who specifically need slower (`-T1` sneaky) or faster
# (`-T4` aggressive) can override per-scan by extending the profile
# table above; the value here is the global default.
DEFAULT_TIMING_TEMPLATE = 3


class DiscoveryCollector(Protocol):
    def discover(self, target_ranges: list[str]) -> list[DiscoveredHost]: ...


class NmapCollector:
    """Wraps `nmap -oX -`. Requires nmap installed on the host running
    VEXUS. Only ever invoked after scope validation (see discovery/scope.py) —
    this class itself does not check authorization.

    Construct with a `profile` (the primary API) for an enum-driven,
    auditable scan technique. The legacy `extra_args` constructor
    parameter is retained for backwards compatibility with existing
    callers/tests but is no longer the primary API: when both are
    provided, `extra_args` extends the profile's flag set (so a test
    stub can still inject `-n` for DNS skip etc. without needing to
    define a new profile)."""

    def __init__(
        self,
        profile: ScanProfile | str | None = None,
        extra_args: list[str] | None = None,
        timeout_seconds: int = 1800,
    ):
        # Normalize string -> enum (the API boundary takes str; this
        # keeps the constructor tolerant of either form).
        if profile is None:
            self.profile = ScanProfile.STEALTH_SYN
        elif isinstance(profile, ScanProfile):
            self.profile = profile
        else:
            try:
                self.profile = ScanProfile(profile)
            except ValueError as exc:
                raise ValueError(
                    f"Unknown scan profile '{profile}'. Valid profiles: "
                    f"{[p.value for p in ScanProfile]}."
                ) from exc

        self.extra_args = list(extra_args) if extra_args else []
        # Profile-driven scans (service_version / os_detect / full) do
        # significantly more probing per host — give them a longer
        # subprocess ceiling by default. The explicit constructor
        # argument still wins when provided by a caller with a
        # maintenance-window budget.
        if timeout_seconds is None or timeout_seconds == 300:
            # backwards-compat default for callers that passed the old
            # 300s value blindly — bump to a profile-appropriate ceiling.
            if self.profile in (ScanProfile.FULL, ScanProfile.OS_DETECT, ScanProfile.SERVICE_VERSION):
                timeout_seconds = 3600
            else:
                timeout_seconds = 900
        self.timeout_seconds = timeout_seconds

    @property
    def nmap_args(self) -> list[str]:
        """The assembled nmap argument list (without the `nmap` binary
        itself or the target ranges). Exposed for testability — tests
        assert on this list rather than parsing `subprocess.run`
        call args."""
        return [*_PROFILE_FLAGS[self.profile], *self.extra_args]

    def discover(self, target_ranges: list[str]) -> list[DiscoveredHost]:
        if shutil.which("nmap") is None:
            raise RuntimeError(
                "nmap is not installed on this host. Install it (e.g. `apt install nmap`) "
                "or configure a different DiscoveryCollector."
            )

        cmd = ["nmap", "-oX", "-", *self.nmap_args, *target_ranges]
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


class PythonTcpCollector:
    """Dependency-free fallback for environments without Nmap.

    A host is reported when it accepts a TCP connection on one of the
    configured ports. Silent hosts remain undiscovered by design.
    """

    def __init__(
        self,
        ports: list[int] | None = None,
        timeout_seconds: float = 0.35,
        max_workers: int = 64,
    ):
        self.ports = ports or [22, 80, 443, 445, 3389, 8000, 8080]
        self.timeout_seconds = timeout_seconds
        self.max_workers = max_workers

    def discover(self, target_ranges: list[str]) -> list[DiscoveredHost]:
        from ipaddress import ip_network

        addresses = [
            str(host)
            for target in target_ranges
            for host in ip_network(target, strict=False).hosts()
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = executor.map(self._probe_host, addresses)
        return [host for host in results if host is not None]

    def _probe_host(self, ip_address: str) -> DiscoveredHost | None:
        for port in self.ports:
            try:
                with socket.create_connection((ip_address, port), timeout=self.timeout_seconds):
                    return DiscoveredHost(ip_address=ip_address, hostname=self._reverse_hostname(ip_address))
            except (ConnectionRefusedError, OSError, TimeoutError):
                continue
        return None

    @staticmethod
    def _reverse_hostname(ip_address: str) -> str | None:
        try:
            hostname, _, _ = socket.gethostbyaddr(ip_address)
            return hostname
        except (socket.herror, socket.gaierror, OSError):
            return None


class SimulatedCollector:
    """Test-only collector. Returns a fixed, caller-supplied host list
    instead of touching the network. Not reachable via the API."""

    def __init__(self, hosts: list[DiscoveredHost] | None = None):
        self._hosts = hosts or []

    def discover(self, target_ranges: list[str]) -> list[DiscoveredHost]:
        return list(self._hosts)
