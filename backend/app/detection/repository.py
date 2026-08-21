from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.models import DetectionRuleConfig


class DetectionRuleConfigRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_rule_key(self, rule_key: str) -> DetectionRuleConfig | None:
        return self.db.scalar(select(DetectionRuleConfig).where(DetectionRuleConfig.rule_key == rule_key))

    def list_all(self) -> list[DetectionRuleConfig]:
        return list(self.db.scalars(select(DetectionRuleConfig)))

    def create(self, **kwargs) -> DetectionRuleConfig:
        config = DetectionRuleConfig(**kwargs)
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def update(self, config: DetectionRuleConfig, **kwargs) -> DetectionRuleConfig:
        for key, value in kwargs.items():
            setattr(config, key, value)
        self.db.commit()
        self.db.refresh(config)
        return config
