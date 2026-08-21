"""
Monitoring collectors.

Same pattern as discovery/collectors.py: a `MonitoringCollector` Protocol
so the active-probing backend is swappable (ICMP today; SNMP or agent
push later) without touching MonitoringService. `SimulatedCollector`
exists for tests only and is not reachable via the API.
"""
import platform
import re
import subprocess
from dataclasses import dataclass
from typing import Protocol


@dataclass
class MonitoringResult:
    available: bool
    latency_ms: float | None = None
    packet_loss_pct: float | None = None


class MonitoringCollector(Protocol):
    def check(self, ip_address: str) -> MonitoringResult: ...


class PingCollector:
    """ICMP-based availability/latency/packet-loss check via the system
    `ping` binary. Requires the process to have permission to send ICMP
    (usually fine unprivileged on Linux with the default ping_group_range,
    and fine by default on Windows/macOS).

    Windows' `ping` uses different flags and output than Linux/macOS
    (`-n`/`-w` with a millisecond timeout vs. `-c`/`-W` with a second
    timeout, and "Reply from ... time=Xms" / "Lost = N (X% loss)" instead
    of the Linux/macOS "X% packet loss" / "time=X ms" format), so both are
    handled explicitly rather than assuming one platform."""

    def __init__(self, count: int = 1, timeout_seconds: int = 2):
        self.count = count
        self.timeout_seconds = timeout_seconds
        self._is_windows = platform.system().lower() == "windows"

    def check(self, ip_address: str) -> MonitoringResult:
        if self._is_windows:
            cmd = ["ping", "-n", str(self.count), "-w", str(self.timeout_seconds * 1000), ip_address]
        else:
            cmd = ["ping", "-c", str(self.count), "-W", str(self.timeout_seconds), ip_address]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds * self.count + 5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return MonitoringResult(available=False, packet_loss_pct=100.0)

        output = result.stdout
        return self._parse_windows(output) if self._is_windows else self._parse_unix(output, result.returncode)

    @staticmethod
    def _parse_unix(output: str, returncode: int) -> MonitoringResult:
        loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
        packet_loss = float(loss_match.group(1)) if loss_match else (0.0 if returncode == 0 else 100.0)

        latency_match = re.search(r"time=([\d.]+)\s*ms", output)
        latency = float(latency_match.group(1)) if latency_match else None

        available = returncode == 0 and packet_loss < 100.0
        return MonitoringResult(available=available, latency_ms=latency, packet_loss_pct=packet_loss)

    @staticmethod
    def _parse_windows(output: str) -> MonitoringResult:
        # "Packets: Sent = 1, Received = 1, Lost = 0 (0% loss)"
        loss_match = re.search(r"\((\d+)%\s*loss\)", output)
        packet_loss = float(loss_match.group(1)) if loss_match else 100.0

        # "time=1ms" or "time<1ms"
        latency_match = re.search(r"time[=<]([\d.]+)\s*ms", output)
        latency = float(latency_match.group(1)) if latency_match else None

        available = packet_loss < 100.0
        return MonitoringResult(available=available, latency_ms=latency, packet_loss_pct=packet_loss)


class SimulatedCollector:
    """Test-only collector. Returns a fixed, caller-supplied result per IP
    (defaulting to unavailable for anything not explicitly listed) instead
    of touching the network. Not reachable via the API."""

    def __init__(self, results: dict[str, MonitoringResult] | None = None):
        self._results = results or {}

    def check(self, ip_address: str) -> MonitoringResult:
        return self._results.get(ip_address, MonitoringResult(available=False, packet_loss_pct=100.0))
