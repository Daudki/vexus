from app.ai.base import AIProvider, AIResponse, Message, ToolCall
from app.ai.providers.mock import MockAIProvider


def get_ai_provider() -> AIProvider:
    """Factory to get the configured AI provider."""
    from app.config.settings import settings
    
    if settings.AI_PROVIDER == "deepseek" and settings.DEEPSEEK_API_KEY:
        from app.ai.providers.deepseek import DeepSeekProvider
        return DeepSeekProvider()
    elif settings.AI_PROVIDER == "cloud":
        from app.ai.providers.cloud import CloudAIProvider
        return CloudAIProvider()
    elif settings.AI_PROVIDER == "local":
        from app.ai.providers.local import LocalAIProvider
        return LocalAIProvider()
    else:
        # Default to mock if no API key or provider specified
        return MockAIProvider()


__all__ = [
    "AIProvider",
    "AIResponse", 
    "Message",
    "ToolCall",
    "get_ai_provider",
]