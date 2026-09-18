from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.incidents.models import Incident, IncidentAlert, IncidentAsset, IncidentStatus, InvestigationNote


class IncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, incident_id: str) -> Incident | None:
        return self.db.get(Incident, incident_id)

    def list_all(
        self,
        status: IncidentStatus | None = None,
        limit: int = 100,
        offset: int = 0,
        include_synthetic: bool = False,
    ) -> list[Incident]:
        query = select(Incident)
        if status:
            query = query.where(Incident.status == status)
        if not include_synthetic:
            query = query.where(Incident.is_synthetic.is_(False))
        query = query.order_by(desc(Incident.updated_at)).limit(limit).offset(offset)
        return list(self.db.scalars(query))

    def create(self, **kwargs) -> Incident:
        incident = Incident(**kwargs)
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def update(self, incident: Incident, **kwargs) -> Incident:
        for key, value in kwargs.items():
            setattr(incident, key, value)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    # --- Alert links ---

    def link_alert(self, incident_id: str, alert_id: str, when) -> IncidentAlert:
        link = IncidentAlert(incident_id=incident_id, alert_id=alert_id, linked_at=when)
        self.db.add(link)
        self.db.commit()
        return link

    def get_alert_link(self, incident_id: str, alert_id: str) -> IncidentAlert | None:
        query = select(IncidentAlert).where(
            IncidentAlert.incident_id == incident_id, IncidentAlert.alert_id == alert_id
        )
        return self.db.scalar(query)

    def list_alert_links(self, incident_id: str) -> list[IncidentAlert]:
        return list(self.db.scalars(select(IncidentAlert).where(IncidentAlert.incident_id == incident_id)))

    def unlink_alert(self, link: IncidentAlert) -> None:
        self.db.delete(link)
        self.db.commit()

    # --- Asset links ---

    def link_asset(self, incident_id: str, asset_id: str, when) -> IncidentAsset:
        link = IncidentAsset(incident_id=incident_id, asset_id=asset_id, linked_at=when)
        self.db.add(link)
        self.db.commit()
        return link

    def get_asset_link(self, incident_id: str, asset_id: str) -> IncidentAsset | None:
        query = select(IncidentAsset).where(
            IncidentAsset.incident_id == incident_id, IncidentAsset.asset_id == asset_id
        )
        return self.db.scalar(query)

    def list_asset_links(self, incident_id: str) -> list[IncidentAsset]:
        return list(self.db.scalars(select(IncidentAsset).where(IncidentAsset.incident_id == incident_id)))

    def unlink_asset(self, link: IncidentAsset) -> None:
        self.db.delete(link)
        self.db.commit()

    # --- Notes (append-only) ---

    def add_note(self, **kwargs) -> InvestigationNote:
        note = InvestigationNote(**kwargs)
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def list_notes(self, incident_id: str) -> list[InvestigationNote]:
        query = (
            select(InvestigationNote)
            .where(InvestigationNote.incident_id == incident_id)
            .order_by(InvestigationNote.created_at)
        )
        return list(self.db.scalars(query))
