import json
import re
from dataclasses import dataclass
from typing import Any

_SPLIT = re.compile(r"(?<!\\):")
_TOKEN = re.compile(r"\d+|[a-z]+")
_PRERELEASE = {"alpha", "beta", "rc", "pre", "dev", "preview"}


@dataclass(frozen=True)
class ParsedCpe:
    part: str
    vendor: str
    product: str
    version: str


def _clean(value: str) -> str:
    return value.replace("\\", "").strip().lower()


def parse_cpe(value: str | None) -> ParsedCpe | None:
    if not value:
        return None
    text = value.strip()
    if text.startswith("cpe:2.3:"):
        parts = _SPLIT.split(text)
        if len(parts) < 6:
            return None
        part, vendor, product, version = parts[2], parts[3], parts[4], parts[5]
    elif text.startswith("cpe:/"):
        parts = text[len("cpe:/"):].split(":")
        if len(parts) < 3:
            return None
        part, vendor, product = parts[0], parts[1], parts[2]
        version = parts[3] if len(parts) > 3 else "*"
    else:
        return None
    if not part or not vendor or not product:
        return None
    return ParsedCpe(_clean(part), _clean(vendor), _clean(product), _clean(version) or "*")


def _tokens(version: str) -> list[int | str]:
    return [int(t) if t.isdigit() else t for t in _TOKEN.findall(version.lower())]


def compare_versions(a: str, b: str) -> int:
    ta, tb = _tokens(a), _tokens(b)
    for x, y in zip(ta, tb):
        if x == y:
            continue
        if isinstance(x, int) and isinstance(y, int):
            return -1 if x < y else 1
        if isinstance(x, str) and isinstance(y, str):
            if x in _PRERELEASE and y not in _PRERELEASE:
                return -1
            if y in _PRERELEASE and x not in _PRERELEASE:
                return 1
            return -1 if x < y else 1
        return -1 if isinstance(x, int) else 1
    if len(ta) == len(tb):
        return 0
    longer, sign = (ta, 1) if len(ta) > len(tb) else (tb, -1)
    extra = longer[min(len(ta), len(tb))]
    if isinstance(extra, str) and extra in _PRERELEASE:
        return -sign
    return sign


def _in_range(version: str, match: dict[str, Any]) -> bool:
    if match.get("versionStartIncluding") and compare_versions(version, match["versionStartIncluding"]) < 0:
        return False
    if match.get("versionStartExcluding") and compare_versions(version, match["versionStartExcluding"]) <= 0:
        return False
    if match.get("versionEndIncluding") and compare_versions(version, match["versionEndIncluding"]) > 0:
        return False
    if match.get("versionEndExcluding") and compare_versions(version, match["versionEndExcluding"]) >= 0:
        return False
    return True


def _cpe_matches(configurations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    stack = list(configurations)
    while stack:
        node = stack.pop()
        for match in node.get("cpeMatch", []) or []:
            if match.get("vulnerable") is True:
                found.append(match)
        stack.extend(node.get("children", []) or [])
        stack.extend(node.get("nodes", []) or [])
    return found


def cve_affects_service(raw_data: str | dict[str, Any] | None, service: ParsedCpe) -> bool:
    if service.version in ("", "*", "-"):
        return False
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except json.JSONDecodeError:
            return False
    if not isinstance(raw_data, dict) or raw_data.get("_truncated"):
        return False
    for match in _cpe_matches(raw_data.get("configurations") or []):
        criteria = parse_cpe(match.get("criteria"))
        if criteria is None:
            continue
        if (criteria.part, criteria.vendor, criteria.product) != (service.part, service.vendor, service.product):
            continue
        if criteria.version == "-":
            continue
        if criteria.version == "*":
            if _in_range(service.version, match):
                return True
            continue
        if compare_versions(criteria.version, service.version) == 0:
            return True
    return False
