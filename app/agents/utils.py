"""
app/agents/utils.py
-------------------
Utility functions for AI response parsing and channel-specific formatting.
"""
import re
import json
from app.core.logging import get_logger

logger = get_logger("AgentUtils")

def to_whatsapp_style(text: str) -> str:
    """
    Converts GitHub-style Markdown to WhatsApp-compatible formatting.
    - **bold** -> *bold*
    - # Header -> *HEADER*
    - ## Header -> *HEADER*
    - [Link](URL) -> Link: URL
    """
    if not text:
        return ""

    # Convert headers (e.g., # Header or ## Header)
    def header_rep(match):
        header_text = match.group(2).strip().upper()
        return f"\n*{header_text}*\n"
    
    # Matches # or ## at start of line
    text = re.sub(r'^(#+)\s*(.*)$', header_rep, text, flags=re.MULTILINE)

    # Convert **bold** to *bold* (WhatsApp uses * for bold)
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)

    # Convert [Text](URL) to Text: URL
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1: \2', text)

    # Clean up excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def extract_block(text: str, tag: str) -> str:
    """
    Robustly extracts content between [TAG] markers.
    Returns empty string if markers are missing.
    Case-insensitive matches for the markers.
    """
    if not text:
        return ""
    pattern = rf'\[{tag}\](.*?)\[/{tag}\]'
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""

def parse_llm_json(response: str) -> dict:
    """
    Robustly extracts and parses JSON from LLM output.
    Handles cases where JSON is wrapped in markdown code blocks.
    """
    if not response:
        return {}

    # Try to find JSON block in markdown backticks
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    else:
        # Fallback to searching for the first { and last }
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1:
            content = response[start:end+1]
        else:
            content = response

    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON: {e} | Content: {content[:100]}...")
        # Emergency fallback: if it's just raw text, wrap it
        return {"text": response, "image_prompt": "Technical diagram"}

def parse_eval_response(raw: str, topic: str) -> dict:
    """
    Parses evaluating responses specifically for the ScoringAgent.
    Ensures safe fallbacks, score clamping, etc.
    """
    fallback = {"score": 5, "feedback": "Answer received! Keep practicing.", "weak_aspects": []}
    if not raw or not isinstance(raw, str) or not raw.strip():
        return fallback

    # Search for json block
    json_match = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    else:
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end != -1:
            content = raw[start:end+1]
        else:
            return fallback

    try:
        data = json.loads(content)
        
        # Parse and clamp score
        score = data.get("score", 5)
        try:
            score = int(score)
        except (ValueError, TypeError):
            score = 5
        score = max(0, min(10, score))
        
        return {
            "score": score,
            "feedback": to_whatsapp_style(data.get("feedback") or "Good attempt! Keep reviewing the concepts."),
            "weak_aspects": data.get("weak_aspects") if isinstance(data.get("weak_aspects"), list) else []
        }
    except json.JSONDecodeError:
        styled_fallback = fallback.copy()
        styled_fallback["feedback"] = to_whatsapp_style(fallback["feedback"])
        return styled_fallback
