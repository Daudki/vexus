from typing import Dict, Any, List, Optional

from app.ai.base import AIProvider, AIResponse, Message


class LocalAIProvider(AIProvider):
    """Local LLM provider (Ollama, etc.) - placeholder."""
    
    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Placeholder for local provider."""
        raise NotImplementedError("Local AI provider not yet implemented")
    
    async def analyze_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Placeholder for local provider."""
        raise NotImplementedError("Local AI provider not yet implemented")
    
    async def analyze_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Placeholder for local provider."""
        raise NotImplementedError("Local AI provider not yet implemented")