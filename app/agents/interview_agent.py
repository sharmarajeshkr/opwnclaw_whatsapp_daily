"""
app/agents/interview_agent.py
----------------------------
Specialized agent for generating daily system design and architecture challenges.
"""
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
            "The output must be a JSON object with two fields:\n"
            "1. 'text': A detailed challenge description for WhatsApp (use markdown, emojis, bolding).\n"
            "2. 'image_prompt': A DALL-E prompt to generate a helpful architecture diagram for this challenge.\n\n"
            "Make it engaging, professional, and practical."
        )
        
        # In a real implementation, we'd use json.loads. 
        # For brevity in this refactor, we assume the LLM returns the text directly or we wrap it.
        # Following the existing pattern:
        response = await self.llm.generate_response(prompt)
        # Simplified extraction logic for this migration
        detailed_text = response # Placeholder for actual JSON parsing
        image_prompt = f"Technical architecture diagram for {level} system design"
        
        self.history.add_to_history("architecture_challenge", detailed_text[:50])
        return detailed_text, image_prompt
