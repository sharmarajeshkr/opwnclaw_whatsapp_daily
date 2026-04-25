"""
app/agents/deep_dive_agent.py
----------------------------
Specialized agent for generating in-depth technical questions on specific topics.
"""
from app.llm.provider import LLMProvider
from app.database.history import UserHistoryManager
from app.agents.utils import extract_block
from app.core.logging import get_logger

logger = get_logger("DeepDiveAgent")

class DeepDiveAgent:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.llm = LLMProvider()
        self.history = UserHistoryManager(phone_number)

    async def get_deep_dive_with_question(self, topic: str, level: str, week: int, skill_profile: dict) -> tuple[str, str]:
        """Generates a deep-dive message and extracts a specific question for the user to answer."""
        history = self.history.get_history(f"deep_dive:{topic}")
        
        prompt = (
            f"You are a Technical Mentor. Create a 'Deep Dive' module for the topic '{topic}' at a {level} level.\n\n"
            f"Previously asked for this topic: {history[-3:]}.\n\n"
            "Format the message for WhatsApp (markdown, structured). End the message with a clear, specific question "
            "that the user must reply to. Use bolding for the question.\n\n"
            "Return a JSON object with:\n"
            "1. 'full_message': The entire content to send.\n"
            "2. 'question': Just the specific question text extracted from the message."
        )
        
        response = await self.llm.generate_response(prompt)
        
        # Robustly extract JSON from the LLM response
        import re
        import json
        question = "What are your thoughts on this?"
        full_content = response # Fallback
        
        try:
            cleaned = re.sub(r'```[\w]*', '', response).strip()
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                question = data.get("question", question)
                full_content = data.get("full_message", response)
        except Exception as exc:
            logger.warning(f"Could not parse deep dive JSON for {self.phone_number}: {exc}. Sending raw response.")
        
        self.history.add_to_history(f"deep_dive:{topic}", question[:200])
        return question.strip(), full_content
