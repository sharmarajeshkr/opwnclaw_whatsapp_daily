"""
app/agents/news_agent.py
-----------------------
Specialized agent for fetching and rewriting technical news and curated updates.
"""
from app.llm.provider import LLMProvider
from app.database.history import UserHistoryManager
from app.agents.utils import extract_block
from app.core.logging import get_logger

logger = get_logger("NewsAgent")

class NewsAgent:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.llm = LLMProvider()
        self.history = UserHistoryManager(phone_number)

    async def get_curated_content(self, source: str, instruction: str) -> str:
        """Generates a curated news digest or article summary based on an instruction."""
        prompt = (
            f"You are a Tech News Curator. Source category: {source}.\n"
            f"Instruction: {instruction}\n\n"
            "Rewrite the content into a friendly, structured WhatsApp reading list. "
            "Include exact links if provided. Use markdown and formatting for readability."
        )
        
        content = await self.llm.generate_response(prompt)
        self.history.add_to_history(f"news:{source}", content[:50])
        return content
