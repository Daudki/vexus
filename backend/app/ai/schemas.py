import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIQueryLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    query_type: str
    target_type: str
    target_id: str
    question: str
    observed_facts: list[str]
    inferences: list[str]
    hypotheses: list[str]
    recommendations: list[str]
    confidence: float
    provider: str
    created_at: datetime

    @field_validator("observed_facts", "inferences", "hypotheses", "recommendations", mode="before")
    @classmethod
    def _parse_json_list(cls, value):
        if isinstance(value, str):
            return json.loads(value)
        return value


class AskRequest(BaseModel):
    context_type: str = Field(pattern="^(alert|incident|asset)$")
    context_id: str
    question: str = Field(min_length=1, max_length=1024)


class AIStatusRead(BaseModel):
    provider: str
    configured: bool
