"""
app/agents/interview_agent.py
----------------------------
Specialized agent for generating daily system design and architecture challenges.
"""
from app.llm.provider import LLMProvider
from app.database.history import UserHistoryManager
from app.agents.utils import parse_llm_json, to_whatsapp_style
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
            f"You are a Senior System Design Interviewer at a Tier-1 Tech Company. "
            f"Generate a daily architectural 'Challenge of the Day' for a {level} level student "
            f"in Week {week} of their program. Their skill profile is: {skill_profile}.\n\n"
            f"Previously sent topics (avoid these): {history[-5:]}.\n\n"
            "The output must be a JSON object with two fields:\n"
            "1. 'text': A detailed challenge description for WhatsApp.\n"
            "   - Use *bold* (single asterisk) for emphasis.\n"
            "   - Use ALL CAPS for section headers.\n"
            "   - Use Emojis (🔹, ✅, 🏗️) for lists and visual clarity.\n"
            "   - Do NOT use ## or # markdown headers.\n"
            "2. 'image_prompt': A DALL-E prompt to generate a helpful architecture diagram for this challenge.\n\n"
            "Example 'text' structure:\n"
            "🏗️ *CHALLENGE OF THE DAY: KAFKA PARTITIONING*\n\n"
            "Your task is to design a high-throughput... \n\n"
            "🔹 *KEY CONSTRAINTS*\n"
            "1. 100k requests/sec\n"
            "2. Order guarantee for specific keys\n\n"
            "Make it engaging, professional, and practical."
        )
        
        response = await self.llm.generate_response(prompt)
        data = parse_llm_json(response)
        
        detailed_text = to_whatsapp_style(data.get("text", response))
        image_prompt = data.get("image_prompt", f"Technical architecture diagram for {level} system design")
        
        self.history.add_to_history("architecture_challenge", detailed_text[:50])
        return detailed_text, image_prompt
