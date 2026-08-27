from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A tool call from the AI."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class Message:
    """A message in a chat conversation."""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None


@dataclass
class AIResponse:
    """Response from an AI provider."""
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=dict)


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Send a chat completion request."""
        pass
    
    @abstractmethod
    async def analyze_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze an alert and provide explanation."""
        pass
    
    @abstractmethod
    async def analyze_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze an incident and provide investigation guidance."""
        pass