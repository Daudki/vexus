"""
EventIngestionService — the normalization/validation/storage steps of
the VEXUS Network Event Contract for externally-sourced events.

Ingested events become ordinary NetworkEvent rows with
processed_by_detection=False, so they flow into DetectionEngine.run()
exactly like discovery- and monitoring-sourced events — there is no
separate ingestion-specific detection path (VEXUS v2 Development Rules,
"do not introduce a second implementation of the same subsystem").
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.assets.repository import AssetRepository
from app.audit.service import AuditService
from app.events.models import NetworkEvent
from app.events.schemas import EventIngestRequest, IngestedEventResult, MAX_JSON_FIELD_CHARS
from app.users.models import User


class EventIngestionError(ValueError):
    """Raised for a well-formed-but-invalid event (e.g. an evidence/
    metadata payload too large to store). Distinct from pydantic
    validation errors, which are caught by FastAPI before this service
    ever runs."""


class EventIngestionService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.audit = AuditService(db)

    def ingest_one(self, request: EventIngestRequest) -> tuple[NetworkEvent, bool]:
        """Normalize, validate, and store a single event.

        Returns (event, asset_matched). asset_matched is False whenever
        the event carried an ip_address that didn't resolve to a known
        asset -- not an error, just useful for the caller to know their
        data didn't fully land (the raw IP is preserved in
        event_metadata either way, never silently dropped).
        """
        asset_id = request.asset_id
        asset_matched = True
        metadata = dict(request.event_metadata)

        if asset_id is None and request.ip_address:
            asset = self.assets.get_by_ip(request.ip_address)
            if asset is not None:
                asset_id = asset.id
            else:
                asset_matched = False
                metadata["unmatched_ip_address"] = request.ip_address
        elif asset_id is not None and self.assets.get_by_id(asset_id) is None:
            raise EventIngestionError(f"asset_id '{asset_id}' does not exist.")

        evidence_json = json.dumps(request.evidence)
        metadata_json = json.dumps(metadata)
        if len(evidence_json) > MAX_JSON_FIELD_CHARS:
            raise EventIngestionError(f"evidence exceeds the {MAX_JSON_FIELD_CHARS}-character limit.")
        if len(metadata_json) > MAX_JSON_FIELD_CHARS:
            raise EventIngestionError(f"event_metadata exceeds the {MAX_JSON_FIELD_CHARS}-character limit.")

        event = NetworkEvent(
            event_type=request.event_type,
            event_source=request.event_source,
            timestamp=request.timestamp,
            asset_id=asset_id,
            severity=request.severity,
            confidence=request.confidence,
            description=request.description,
            evidence=evidence_json,
            event_metadata=metadata_json,
            # Never trust an external caller's claim about these two:
            # ingested data is real by definition (Simulation Mode is
            # the only legitimate is_synthetic=True writer), and every
            # event must enter the same detection pass as everything
            # else -- there is no "skip detection" ingestion path.
            is_synthetic=False,
            processed_by_detection=False,
        )
        self.db.add(event)
        return event, asset_matched

    def ingest_batch(
        self, requests: list[EventIngestRequest], actor: User | None, ip_address: str = ""
    ) -> list[tuple[NetworkEvent, bool]]:
        """All-or-nothing: if any event in the batch fails validation
        (e.g. an oversized evidence payload), nothing commits and the
        caller gets a single 400 for the whole batch rather than a
        confusing partial ingest. The router is responsible for calling
        db.rollback() when this raises."""
        results = [self.ingest_one(request) for request in requests]
        self.db.commit()
        for event, _ in results:
            self.db.refresh(event)

        source_counts: dict[str, int] = {}
        for request in requests:
            source_counts[request.event_source.value] = source_counts.get(request.event_source.value, 0) + 1
        unmatched = sum(1 for _, matched in results if not matched)

        self.audit.record(
            action="events.ingest",
            actor=actor,
            target_type="network_event",
            target_id="batch",
            detail=(
                f"Ingested {len(results)} event(s) ({source_counts}); "
                f"{unmatched} did not match a known asset by IP."
            ),
            ip_address=ip_address,
        )
        return results

    @staticmethod
    def to_result(event: NetworkEvent, asset_matched: bool) -> IngestedEventResult:
        return IngestedEventResult(event_id=event.id, event_type=event.event_type, asset_matched=asset_matched)
