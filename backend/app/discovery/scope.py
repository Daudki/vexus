"""
Discovery scope validation.

No scan target is ever passed to a collector without first being proven
to fall entirely within an operator-configured authorized range. This
is enforced here, not just documented — `DiscoveryService` calls
`validate_target_ranges` before touching a collector, and there is no
code path that skips it.
"""
import ipaddress

from app.config.settings import get_settings


class ScopeError(Exception):
    pass


def get_authorized_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    settings = get_settings()
    networks = []
    for raw in settings.AUTHORIZED_SCAN_RANGES:
        try:
            networks.append(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            continue  # malformed entries in config are simply not authorized for anything
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
