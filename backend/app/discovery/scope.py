"""
Discovery scope validation.

No scan target is ever passed to a collector without first being proven
to fall entirely within an operator-configured authorized range. This
is enforced here, not just documented — `DiscoveryService` calls
`validate_target_ranges` before touching a collector, and there is no
code path that skips it.
"""
import ipaddress
import logging

from app.config.settings import get_settings

logger = logging.getLogger("vexus.discovery.scope")


class ScopeError(Exception):
    pass


# The whole point of AUTHORIZED_SCAN_RANGES is that an operator
# deliberately, narrowly authorizes what's actually theirs to scan.
# Nothing previously stopped an operator from typing 0.0.0.0/0 (or
# something nearly as broad) — accidentally or as a lazy shortcut —
# and completely defeating that safeguard in one line, since "the
# entire internet" is technically a valid CIDR block. This ceiling
# rejects anything broader than a /8 (already enormous — the entire
# 10.0.0.0/8 RFC1918 block, 16.7 million addresses, is intentionally
# still allowed for organizations that legitimately use all of it) and
# explicitly names the two most common ways to accidentally authorize
# "everything": 0.0.0.0/0 and ::/0.
_MAX_AUTHORIZED_PREFIX_LEN = {4: 8, 6: 32}


def _is_dangerously_broad(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> bool:
    if network.prefixlen == 0:
        return True
    max_len = _MAX_AUTHORIZED_PREFIX_LEN[network.version]
    return network.prefixlen < max_len


def get_authorized_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    settings = get_settings()
    networks = []
    for raw in settings.AUTHORIZED_SCAN_RANGES:
        try:
            network = ipaddress.ip_network(raw, strict=False)
        except ValueError:
            logger.warning("Ignoring malformed AUTHORIZED_SCAN_RANGES entry: %r", raw)
            continue  # malformed entries in config are simply not authorized for anything

        if _is_dangerously_broad(network):
            logger.warning(
                "Ignoring AUTHORIZED_SCAN_RANGES entry %r: broader than the maximum allowed "
                "prefix (/%d for IPv%d). Authorize a narrower range that matches what you "
                "actually administer.",
                raw,
                _MAX_AUTHORIZED_PREFIX_LEN[network.version],
                network.version,
            )
            continue

        networks.append(network)
    return networks


def validate_target_ranges(target_ranges: list[str]) -> None:
    """Raises ScopeError if any target is invalid or outside authorized ranges."""
    if not target_ranges:
        raise ScopeError("No target ranges specified.")

    authorized = get_authorized_networks()
    if not authorized:
        raise ScopeError(
            "No authorized scan ranges are configured (AUTHORIZED_SCAN_RANGES is empty). "
            "An administrator must explicitly authorize CIDR ranges before any scan can run."
        )

    for target in target_ranges:
        try:
            target_network = ipaddress.ip_network(target, strict=False)
        except ValueError as exc:
            raise ScopeError(f"'{target}' is not a valid IP address or CIDR range.") from exc

        if not any(_is_subnet_of(target_network, authorized_net) for authorized_net in authorized):
            raise ScopeError(
                f"Target range '{target}' is not within any authorized scan range. Scan refused."
            )


def _is_subnet_of(candidate, network) -> bool:
    try:
        return candidate.version == network.version and candidate.subnet_of(network)
    except (TypeError, ValueError):
        return False
