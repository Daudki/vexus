from app.monitoring.collectors import PingCollector

WINDOWS_SUCCESS_OUTPUT = """
Pinging 10.0.0.5 with 32 bytes of data:
Reply from 10.0.0.5: bytes=32 time=1ms TTL=64

Ping statistics for 10.0.0.5:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 1ms, Maximum = 1ms, Average = 1ms
"""

WINDOWS_SUB_MS_OUTPUT = """
Pinging 10.0.0.6 with 32 bytes of data:
Reply from 10.0.0.6: bytes=32 time<1ms TTL=64

Ping statistics for 10.0.0.6:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),
"""

WINDOWS_TIMEOUT_OUTPUT = """
Pinging 10.0.0.7 with 32 bytes of data:
Request timed out.

Ping statistics for 10.0.0.7:
    Packets: Sent = 1, Received = 0, Lost = 1 (100% loss),
"""

UNIX_SUCCESS_OUTPUT = """
PING 10.0.0.5 (10.0.0.5) 56(84) bytes of data.
64 bytes from 10.0.0.5: icmp_seq=1 ttl=64 time=0.045 ms

--- 10.0.0.5 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 0.045/0.045/0.045/0.000 ms
"""

UNIX_TIMEOUT_OUTPUT = """
PING 10.0.0.7 (10.0.0.7) 56(84) bytes of data.

--- 10.0.0.7 ping statistics ---
1 packets transmitted, 0 received, 100% packet loss, time 0ms
"""


def test_windows_success_output_is_parsed_correctly():
    result = PingCollector._parse_windows(WINDOWS_SUCCESS_OUTPUT)
    assert result.available is True
    assert result.latency_ms == 1.0
    assert result.packet_loss_pct == 0.0


def test_windows_sub_millisecond_latency_is_parsed():
    result = PingCollector._parse_windows(WINDOWS_SUB_MS_OUTPUT)
    assert result.available is True
    assert result.latency_ms == 1.0  # "time<1ms" -> regex captures the "1"


def test_windows_timeout_output_is_parsed_as_unavailable():
    result = PingCollector._parse_windows(WINDOWS_TIMEOUT_OUTPUT)
    assert result.available is False
    assert result.packet_loss_pct == 100.0
    assert result.latency_ms is None


def test_unix_success_output_is_parsed_correctly():
    result = PingCollector._parse_unix(UNIX_SUCCESS_OUTPUT, returncode=0)
    assert result.available is True
    assert result.latency_ms == 0.045
    assert result.packet_loss_pct == 0.0


def test_unix_timeout_output_is_parsed_as_unavailable():
    result = PingCollector._parse_unix(UNIX_TIMEOUT_OUTPUT, returncode=1)
    assert result.available is False
    assert result.packet_loss_pct == 100.0


def test_platform_detection_selects_correct_parser():
    windows_collector = PingCollector()
    windows_collector._is_windows = True
    result = windows_collector._parse_windows(WINDOWS_SUCCESS_OUTPUT)
    assert result.available is True

    unix_collector = PingCollector()
    unix_collector._is_windows = False
    result = unix_collector._parse_unix(UNIX_SUCCESS_OUTPUT, returncode=0)
    assert result.available is True
