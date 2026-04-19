"""
app/agents/utils.py
-------------------
Shared utilities for AI agents, including robust LLM response parsing
and block extraction logic.
"""
import re
import json
from app.core.logging import get_logger

logger = get_logger("AgentUtils")

def extract_block(text: str, tag: str) -> str:
    """Extract content between [TAG] ... [/TAG] markers (case-insensitive)."""
    pattern = rf'\[{tag}\](.*?)\[/{tag}\]'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""

def parse_eval_response(raw: str, topic: str) -> dict:
    """Safely parse JSON from the LLM evaluation response."""
    try:
        # Strip any accidental markdown code fences
        cleaned = re.sub(r'```[\w]*', '', raw).strip()
        # Extract first JSON object found
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return {
                "score":        max(0, min(10, int(data.get("score", 5)))),
                "feedback":     str(data.get("feedback", "Answer received!")),
                "weak_aspects": list(data.get("weak_aspects", [])),
                "follow_up_question": data.get("follow_up_question"),
                "is_correct":   bool(data.get("is_correct", data.get("score", 0) >= 6))
            }
    except Exception as exc:
        logger.warning(f"Could not parse eval JSON for topic '{topic}': {exc}")
    
    # Safe fallback — never crash the handler
    return {
        "score": 5,
        "feedback": "Answer received! Keep practising 💪",
        "weak_aspects": [],
        "is_correct": False
    }
