from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from app.ai.base import AIProvider, AIResponse, Message, ToolCall


class MockAIProvider(AIProvider):
    """Mock AI provider for development and testing."""
    
    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Return mock chat completion."""
        return AIResponse(
            content="This is a mock AI response. Configure DEEPSEEK_API_KEY in .env for real AI.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )
    
    async def analyze_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return mock alert analysis."""
        return {
            "summary": "Mock analysis: This is a simulated alert analysis.",
            "observed_facts": [
                f"Alert rule: {alert_data.get('rule_name', 'Unknown')}",
                f"Asset affected: {alert_data.get('asset_id', 'Unknown')}",
                f"Severity: {alert_data.get('severity', 'Unknown')}",
            ],
            "inferences": [
                "Mock inference 1: This appears to be a test alert",
                "Mock inference 2: No real threat detected in mock mode",
            ],
            "recommendations": [
                "Set DEEPSEEK_API_KEY in .env for real AI analysis",
                "Review the alert manually in the VEXUS UI",
            ],
            "severity_assessment": alert_data.get('severity', 'Medium'),
            "confidence": 0.5,
            "mitre_tactics": ["TA0001", "TA0002"],
        }
    
    async def analyze_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return mock incident analysis."""
        return {
            "incident_summary": "Mock analysis: This is a simulated incident analysis.",
            "attack_chain": [
                "Mock step 1: Initial detection",
                "Mock step 2: Investigation needed",
                "Mock step 3: Resolution recommended",
            ],
            "impact_assessment": "Mock impact: Low - This is a test incident",
            "investigation_steps": [
                "Review all associated alerts",
                "Check asset status and history",
                "Verify if this is a false positive",
            ],
            "containment_recommendations": [
                "Set DEEPSEEK_API_KEY for real analysis",
                "Document findings in investigation notes",
            ],
            "priority": incident_data.get('priority', 'Medium'),
        }