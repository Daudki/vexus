from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.ai.models import AIQueryLog
from app.ai.provider import AIProvider, AnthropicProvider, DeepSeekProvider, NullProvider, OllamaProvider
from app.ai.schemas import AIQueryLogRead, AIStatusRead, AskRequest
from app.ai.service import AIService, AIServiceError
from app.config.settings import get_settings
from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

_ALLOWED_ROLES = (RoleName.ADMIN, RoleName.SECURITY_ANALYST, RoleName.NETWORK_ADMINISTRATOR)


def get_ai_provider() -> AIProvider:
    """Default provider for the running deployment. Overridden in tests
    to inject a fake provider instead of requiring a real API key."""
    settings = get_settings()
    provider_name = (settings.AI_PROVIDER or "").lower()
    if provider_name in {"none", "mock"}:
        return NullProvider()
    if provider_name == "cloud" and settings.ANTHROPIC_API_KEY:
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, model=settings.CLOUD_AI_MODEL)
    if provider_name == "deepseek" and settings.DEEPSEEK_API_KEY:
        return DeepSeekProvider(api_key=settings.DEEPSEEK_API_KEY, model=settings.DEEPSEEK_MODEL)
    if provider_name == "local":
        return OllamaProvider(
            base_url=settings.LOCAL_AI_URL,
            model=settings.LOCAL_AI_MODEL,
            timeout_seconds=settings.LOCAL_AI_TIMEOUT_SECONDS,
        )
    return NullProvider()


@router.get("/status", response_model=AIStatusRead)
def get_status(_: User = Depends(require_any_role)) -> AIStatusRead:
    settings = get_settings()
    provider_name = (settings.AI_PROVIDER or "").lower()
    if provider_name == "cloud":
        configured = bool(settings.ANTHROPIC_API_KEY)
    elif provider_name == "deepseek":
        configured = bool(settings.DEEPSEEK_API_KEY)
    elif provider_name == "local":
        configured = bool(settings.LOCAL_AI_URL and settings.LOCAL_AI_MODEL)
    else:
        provider_name = "none"
        configured = False
    return AIStatusRead(provider=provider_name, configured=configured)


@router.post("/alerts/{alert_id}/explain", response_model=AIQueryLogRead)
def explain_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    current_user: User = Depends(require_role(*_ALLOWED_ROLES)),
) -> AIQueryLogRead:
    try:
        return AIService(db, provider).explain_alert(alert_id, current_user)
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/incidents/{incident_id}/summarize", response_model=AIQueryLogRead)
def summarize_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    current_user: User = Depends(require_role(*_ALLOWED_ROLES)),
) -> AIQueryLogRead:
    try:
        return AIService(db, provider).summarize_incident(incident_id, current_user)
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/ask", response_model=AIQueryLogRead)
def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    current_user: User = Depends(require_role(*_ALLOWED_ROLES)),
) -> AIQueryLogRead:
    try:
        return AIService(db, provider).ask(payload.context_type, payload.context_id, payload.question, current_user)
    except AIServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/queries", response_model=list[AIQueryLogRead])
def list_queries(
    target_type: str | None = None,
    target_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> list[AIQueryLogRead]:
    query = select(AIQueryLog)
    if target_type:
        query = query.where(AIQueryLog.target_type == target_type)
    if target_id:
        query = query.where(AIQueryLog.target_id == target_id)
    query = query.order_by(desc(AIQueryLog.created_at)).limit(limit)
    return list(db.scalars(query))
