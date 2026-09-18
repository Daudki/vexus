from pydantic import BaseModel


class SimulationStatusRead(BaseModel):
    active: bool
    assets: int
    events: int
    alerts: int
    incidents: int


class SimulationRunRead(BaseModel):
    assets_created: int
    events_created: int
    alerts_created: int
    alerts_updated: int


class SimulationResetRead(BaseModel):
    assets_deleted: int
    events_deleted: int
    alerts_deleted: int
    incidents_deleted: int
