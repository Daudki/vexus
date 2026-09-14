"""Replaceable threat-intelligence providers.

The first adapter targets the NVD 2.0 CVE API. The provider returns a small,
normalized object so the service layer is independent of NVD's JSON schema.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# A CVE ID that only satisfies "starts with CVE-" still allows arbitrary
# trailing content (e.g. "CVE-'; DROP..." -- not a SQL injection risk
# here since the ORM parameterizes it, but it would happily be URL-encoded
# and sent to NVD as a malformed query, and could exceed the
# Vulnerability.cve_id column's String(32) limit and fail with a raw DB
# error instead of a clean validation error). Real CVE IDs always match
# this shape.
_CVE_ID_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,19}$")


class ThreatIntelProviderError(RuntimeError):
    """Raised when a provider cannot return valid threat-intelligence data."""


@dataclass(frozen=True)
class VulnerabilityRecord:
    cve_id: str
    source: str
    description: str
    cvss_score: float | None
    cvss_severity: str | None
    cvss_version: str | None
    published_at: datetime | None
    last_modified_at: datetime | None
    cwe_ids: list[str]
    affected_cpes: list[str]
    references: list[str]
    raw_data: dict[str, Any]
    is_rejected: bool


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _first_metric(metrics: dict[str, Any]) -> tuple[float | None, str | None, str | None]:
    # Prefer the newest CVSS generation available from NVD.
    for key, version in (("cvssMetricV40", "4.0"), ("cvssMetricV31", "3.1"), ("cvssMetricV30", "3.0")):
        entries = metrics.get(key) or []
        if not entries:
            continue
        cvss = entries[0].get("cvssData") or {}
        score = cvss.get("baseScore")
        severity = cvss.get("baseSeverity")
        try:
            parsed_score = float(score) if score is not None else None
        except (TypeError, ValueError):
            # NVD's shape is generally reliable, but a provider response
            # is still external, untrusted input -- a malformed score
            # must not turn into an unhandled 500 for the whole sync.
            parsed_score = None
        return (parsed_score, severity, version)
    return None, None, None


def _collect_cpes(configurations: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    stack = list(configurations)
    while stack:
        node = stack.pop()
        for match in node.get("cpeMatch", []) or []:
            criteria = match.get("criteria")
            if criteria and criteria not in seen:
                seen.add(criteria)
                found.append(criteria)
        stack.extend(node.get("children", []) or [])
        stack.extend(node.get("nodes", []) or [])
    return found


class NVDProvider:
    name = "nvd"

    def __init__(self, base_url: str, api_key: str | None = None, timeout_seconds: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def fetch_cve(self, cve_id: str) -> VulnerabilityRecord:
        normalized = cve_id.strip().upper()
        if not _CVE_ID_PATTERN.match(normalized):
            raise ThreatIntelProviderError("CVE ID must look like 'CVE-YYYY-NNNN' (4+ digit sequence number).")

        params = urlencode({"cveId": normalized})
        url = f"{self.base_url}/cves/2.0?{params}"
        headers = {"Accept": "application/json", "User-Agent": "VEXUS-ThreatIntel/2.0"}
        if self.api_key:
            headers["apiKey"] = self.api_key
        request = Request(url, headers=headers, method="GET")

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ThreatIntelProviderError(f"NVD returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError) as exc:
            raise ThreatIntelProviderError(f"NVD request failed: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ThreatIntelProviderError("NVD returned invalid JSON.") from exc

        vulnerabilities = payload.get("vulnerabilities") or []
        if not vulnerabilities:
            raise ThreatIntelProviderError(f"CVE '{normalized}' was not found in NVD.")

        cve = vulnerabilities[0].get("cve") or {}
        descriptions = cve.get("descriptions") or []
        description = next((d.get("value", "") for d in descriptions if d.get("lang") == "en"), "")
        score, severity, version = _first_metric(cve.get("metrics") or {})

        cwe_ids: list[str] = []
        for weakness in cve.get("weaknesses") or []:
            for item in weakness.get("description") or []:
                value = item.get("value")
                if value and value not in cwe_ids:
                    cwe_ids.append(value)

        references: list[str] = []
        for reference in cve.get("references") or []:
            url_value = reference.get("url")
            if url_value and url_value not in references:
                references.append(url_value)

        return VulnerabilityRecord(
            cve_id=cve.get("id", normalized),
            source=self.name,
            description=description,
            cvss_score=score,
            cvss_severity=severity,
            cvss_version=version,
            published_at=_parse_datetime(cve.get("published")),
            last_modified_at=_parse_datetime(cve.get("lastModified")),
            cwe_ids=cwe_ids,
            affected_cpes=_collect_cpes(cve.get("configurations") or []),
            references=references,
            raw_data=cve,
            is_rejected=bool(cve.get("vulnStatus") == "Rejected"),
        )
