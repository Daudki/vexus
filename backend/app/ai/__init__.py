from app.ai.base import AIProvider, AIResponse, Message, ToolCall
from app.ai.providers.deepseek import DeepSeekProvider
from app.ai.providers.mock import MockAIProvider


def get_ai_provider() -> AIProvider:
    """Factory to get the configured AI provider."""
    from app.config import settings
    
    if settings.AI_PROVIDER == "deepseek":
        return DeepSeekProvider()
    elif settings.AI_PROVIDER == "cloud":
        # Future cloud provider (Anthropic/OpenAI)
        from app.ai.providers.cloud import CloudAIProvider
        return CloudAIProvider()
    elif settings.AI_PROVIDER == "local":
        # Future local LLM provider
        from app.ai.providers.local import LocalAIProvider
        return LocalAIProvider()
    else:
        # Default: mock if no API key, otherwise deepseek
        if settings.DEEPSEEK_API_KEY:
            return DeepSeekProvider()
        return MockAIProvider()