"""
app/agents/scoring_agent.py
--------------------------
Specialized agent for evaluating user answers and providing scoring/feedback.
"""
import json
from app.llm.provider import LLMProvider
from app.core.logging import get_logger

from app.agents.utils import parse_eval_response
from app.core.logging import get_logger

logger = get_logger("ScoringAgent")

class ScoringAgent:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.llm = LLMProvider()

    async def evaluate_answer(self, question: str, user_answer: str, topic: str, level: str) -> dict:
        """Scores a user's answer and provides constructive feedback."""
        prompt = (
            f"You are a Senior Technical Interviewer. Evaluate the following user answer for the topic '{topic}' at a {level} level.\n\n"
            f"Question: {question}\n"
            f"User Answer: {user_answer}\n\n"
            "Return a JSON object with:\n"
            "1. 'score': Integer 0-10\n"
            "2. 'feedback': A concise, encouraging, and technical critique (WhatsApp markdown)\n"
            "3. 'weak_aspects': A list of concepts the user missed or misunderstood\n"
            "4. 'is_correct': Boolean\n"
        )
        
        response = await self.llm.generate_response(prompt)
        return parse_eval_response(response, topic)
