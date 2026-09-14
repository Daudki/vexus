import json

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.threat_intel.models import Vulnerability

# raw_data is an unbounded Text column (no hard DB limit like the
# String(4096) columns used elsewhere), but "unbounded" shouldn't mean
# "no ceiling at all" -- a malformed or unexpectedly huge provider
# response (a provider bug, or a future adapter with much larger
# payloads) is truncated with a note rather than stored in full, so one
# pathological CVE record can't cause unbounded row growth. Real NVD
# payloads are generally well under this.
_MAX_RAW_DATA_CHARS = 200_000


class VulnerabilityRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_cve(self, cve_id: str) -> Vulnerability | None:
        return self.db.scalar(select(Vulnerability).where(Vulnerability.cve_id == cve_id.upper()))

    def list(self, search: str | None = None, severity: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[Vulnerability], int]:
        query = select(Vulnerability)
        if search:
            like = f"%{search}%"
            query = query.where(or_(Vulnerability.cve_id.ilike(like), Vulnerability.description.ilike(like)))
        if severity:
            query = query.where(Vulnerability.cvss_severity == severity.upper())

        # A previous version did `len(list(self.db.scalars(query)))` to
        # get the total -- loading every matching row into memory just
        # to count them, on every single call to this endpoint. With
        # NVD's real CVE volume (200,000+ records) this would become a
        # genuine resource-exhaustion vector, not just an inefficiency.
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0

        rows = query.order_by(desc(Vulnerability.last_modified_at)).limit(limit).offset(offset)
        return list(self.db.scalars(rows)), total

    def upsert(self, record) -> tuple[Vulnerability, bool, bool]:
        existing = self.get_by_cve(record.cve_id)
        created = existing is None
        updated = False
        raw_json = json.dumps(record.raw_data, separators=(",", ":"), sort_keys=True)
        if len(raw_json) > _MAX_RAW_DATA_CHARS:
            raw_json = json.dumps(
                {"_truncated": True, "_original_length": len(raw_json)},
                separators=(",", ":"),
            )
        if existing is None:
            existing = Vulnerability(cve_id=record.cve_id.upper())
            self.db.add(existing)
        else:
            updated = existing.raw_data != raw_json

        existing.source = record.source
        existing.description = record.description
        existing.cvss_score = record.cvss_score
        existing.cvss_severity = record.cvss_severity
        existing.cvss_version = record.cvss_version
        existing.published_at = record.published_at
        existing.last_modified_at = record.last_modified_at
        existing.cwe_ids = json.dumps(record.cwe_ids)
        existing.affected_cpes = json.dumps(record.affected_cpes)
        existing.references = json.dumps(record.references)
        existing.raw_data = raw_json
        existing.is_rejected = record.is_rejected
        self.db.flush()
        return existing, created, updated
