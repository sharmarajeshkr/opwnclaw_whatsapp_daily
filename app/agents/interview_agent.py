"""
app/agents/interview_agent.py
----------------------------
Specialized agent for generating daily system design and architecture challenges.
"""
import re
import json
from app.llm.provider import LLMProvider
from app.database.history import UserHistoryManager
from app.core.logging import get_logger

logger = get_logger("InterviewAgent")

class InterviewAgent:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.llm = LLMProvider()
        self.history = UserHistoryManager(phone_number)

    async def get_daily_challenge(self, level: str, week: int, skill_profile: dict) -> tuple[str, str]:
        """Generates a system design challenge tailored to level and progress."""
        history = self.history.get_history("architecture_challenge")
        
        prompt = (
            f"You are a Senior System Design Interviewer. Generate a daily architectural 'Challenge of the Day' for a {level} level student "
            f"in Week {week} of their program. Their skill profile is: {skill_profile}.\n\n"
            f"Previously sent topics (avoid these): {history[-5:]}.\n\n"
            "The output must be a valid JSON object with exactly two fields:\n"
            "1. 'text': A detailed challenge description for WhatsApp (use emojis and bold with *asterisks*, not markdown #headers).\n"
            "2. 'programing question from Leet.code for easy leavl, medium and hard leavl and  '\n"
            "Respond with ONLY the JSON object, no extra text or code fences."
        )
        
        response = await self.llm.generate_response(prompt)
        
        # Robustly extract JSON from the LLM response
        detailed_text = response  # fallback: send raw if parsing fails
        programing_question = f"Technical architecture diagram for {level} system design"
        try:
            cleaned = re.sub(r'```[\w]*', '', response).strip()
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                detailed_text = data.get("text", response)
                programing_question = data.get("programing question from Leet.code for easy leavl, medium and hard leavl and  ", programing_question)
        except Exception as exc:
            logger.warning(f"Could not parse challenge JSON for {self.phone_number}: {exc}. Sending raw response.")
        
        self.history.add_to_history("architecture_challenge", detailed_text[:50])
        return detailed_text, programing_question
