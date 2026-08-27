import json
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.ai.base import AIProvider, AIResponse, Message, ToolCall


class DeepSeekProvider(AIProvider):
    """DeepSeek API provider for VEXUS AI."""
    
    def __init__(self):
        from app.config.settings import settings
        
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = "https://api.deepseek.com/v1"
        self.model = settings.DEEPSEEK_MODEL or "deepseek-chat"
        self.client = httpx.Client(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )
    
    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Send a chat completion request to DeepSeek."""
        
        # Convert our Message format to DeepSeek format
        formatted_messages = []
        for msg in messages:
            formatted = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                formatted["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        }
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                formatted["tool_call_id"] = msg.tool_call_id
            formatted_messages.append(formatted)
        
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    }
                }
                for tool in tools
            ]
            payload["tool_choice"] = "auto"
        
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            
            return self._parse_response(data)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception("Invalid DeepSeek API key. Please check your DEEPSEEK_API_KEY.")
            elif e.response.status_code == 429:
                raise Exception("DeepSeek rate limit exceeded. Please try again later.")
            else:
                raise Exception(f"DeepSeek API error: {e.response.text}")
        except Exception as e:
            raise Exception(f"DeepSeek request failed: {str(e)}")
    
    async def analyze_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze an alert and provide explanation."""
        
        prompt = self._build_alert_analysis_prompt(alert_data)
        
        messages = [
            Message(
                role="system",
                content="""You are VEXUS AI, a security intelligence assistant. 
                Analyze security alerts with these rules:
                1. Only use the evidence provided - never fabricate facts
                2. Separate Observed Facts from Inferences
                3. Provide actionable recommendations
                4. Be concise but thorough
                5. Use MITRE ATT&CK references where relevant
                
                Format your response as JSON with these fields:
                {
                    "summary": "Brief 1-2 sentence summary",
                    "observed_facts": ["fact1", "fact2"],
                    "inferences": ["inference1", "inference2"],
                    "recommendations": ["recommendation1", "recommendation2"],
                    "severity_assessment": "Critical/High/Medium/Low/Info",
                    "confidence": 0.0-1.0,
                    "mitre_tactics": ["TA0001", "TA0002"]
                }"""
            ),
            Message(
                role="user",
                content=prompt
            )
        ]
        
        response = await self.chat_completion(messages, temperature=0.3, max_tokens=2000)
        
        try:
            # Try to parse JSON from the response
            content = response.content.strip()
            # Handle markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback: return structured text
            return {
                "summary": response.content[:200],
                "observed_facts": ["AI analysis available in raw format"],
                "inferences": [],
                "recommendations": ["Enable JSON parsing or check API response"],
                "severity_assessment": alert_data.get('severity', 'Unknown'),
                "confidence": 0.5,
                "mitre_tactics": []
            }
    
    async def analyze_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze an incident and provide investigation guidance."""
        
        prompt = self._build_incident_analysis_prompt(incident_data)
        
        messages = [
            Message(
                role="system",
                content="""You are VEXUS AI, a security incident investigator.
                Analyze security incidents with these rules:
                1. Correlate evidence from multiple alerts
                2. Identify attack patterns
                3. Suggest investigation steps
                4. Recommend containment actions
                
                Format as JSON:
                {
                    "incident_summary": "What happened",
                    "attack_chain": ["step1", "step2", "step3"],
                    "impact_assessment": "Description of impact",
                    "investigation_steps": ["step1", "step2"],
                    "containment_recommendations": ["rec1", "rec2"],
                    "priority": "Critical/High/Medium/Low"
                }"""
            ),
            Message(
                role="user",
                content=prompt
            )
        ]
        
        response = await self.chat_completion(messages, temperature=0.3, max_tokens=2000)
        
        try:
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "incident_summary": response.content[:300],
                "attack_chain": [],
                "impact_assessment": "Unknown",
                "investigation_steps": [],
                "containment_recommendations": [],
                "priority": incident_data.get('priority', 'Medium')
            }
    
    def _build_alert_analysis_prompt(self, alert_data: Dict[str, Any]) -> str:
        """Build the prompt for alert analysis."""
        
        prompt = f"""
        Analyze this security alert from VEXUS:
        
        ALERT DETAILS:
        - Rule: {alert_data.get('rule_name', 'Unknown')}
        - Severity: {alert_data.get('severity', 'Unknown')}
        - Asset: {alert_data.get('asset_id', 'Unknown')}
        - Status: {alert_data.get('status', 'New')}
        - Confidence: {alert_data.get('confidence', 0.0)}
        - Count: {alert_data.get('count', 1)}
        
        EVIDENCE:
        {json.dumps(alert_data.get('evidence', {}), indent=2)}
        """
        
        if alert_data.get('events'):
            prompt += f"\n\nRELATED EVENTS:\n{json.dumps(alert_data.get('events', []), indent=2)}"
        
        prompt += "\n\nProvide analysis following the required JSON format."
        return prompt
    
    def _build_incident_analysis_prompt(self, incident_data: Dict[str, Any]) -> str:
        """Build the prompt for incident analysis."""
        
        prompt = f"""
        Analyze this security incident from VEXUS:
        
        INCIDENT DETAILS:
        - Title: {incident_data.get('title', 'Unknown')}
        - Severity: {incident_data.get('severity', 'Unknown')}
        - Priority: {incident_data.get('priority', 'Unknown')}
        - Status: {incident_data.get('status', 'New')}
        - Assets: {incident_data.get('asset_ids', [])}
        
        ALERTS IN INCIDENT:
        {json.dumps(incident_data.get('alerts', []), indent=2)[:2000]}
        """
        
        prompt += "\n\nProvide investigation guidance following the required JSON format."
        return prompt
    
    def _parse_response(self, data: Dict[str, Any]) -> AIResponse:
        """Parse DeepSeek API response into our format."""
        
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        
        tool_calls = []
        for tc in message.get("tool_calls", []):
            try:
                arguments = json.loads(tc.get("function", {}).get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}
            
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=tc.get("function", {}).get("name", ""),
                    arguments=arguments,
                )
            )
        
        return AIResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            usage={
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": data.get("usage", {}).get("total_tokens", 0),
            },
        )