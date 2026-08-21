"""
AIQueryLog — every AI interaction, persisted.

This is both the audit trail (who asked what, when, and what the model
said) and what lets the frontend show past explanations without
re-calling the API. Facts/inferences/hypotheses/recommendations are
stored as JSON-encoded lists — kept structurally separate at the
storage layer, not flattened into one blob, so "what did the AI claim
was an observed fact vs. a hypothesis" stays answerable later.
"""
from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AIQueryLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_query_logs"

    query_type: Mapped[str] = mapped_column(String(32))  # explain_alert | summarize_incident | ask
    target_type: Mapped[str] = mapped_column(String(32))  # alert | incident | asset
    target_id: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(String(1024), default="")

    observed_facts: Mapped[str] = mapped_column(String(4096), default="[]")
    inferences: Mapped[str] = mapped_column(String(4096), default="[]")
    hypotheses: Mapped[str] = mapped_column(String(4096), default="[]")
    recommendations: Mapped[str] = mapped_column(String(4096), default="[]")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(16), default="none")
