"""
app/agents/curator_agent.py
-----------------------
Specialized agent for fetching and rewriting technical articles, blogs, and curated updates.
"""
from app.llm.provider import LLMProvider
from app.database.history import UserHistoryManager
from app.agents.utils import extract_block
from app.core.logging import get_logger

logger = get_logger("CuratorAgent")

class CuratorAgent:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.llm = LLMProvider()
        self.history = UserHistoryManager(phone_number)

    async def get_best_medium_tag(self, topic: str) -> str:
        """Uses AI to predict the best Medium.com tag for a given topic string."""
        prompt = (
            f"Given the topic: '{topic}', what is the single most relevant Medium.com tag? "
            "Respond with ONLY the tag (lowercase, hyphenated if multiple words, no quotes or punctuation). "
            "Example: 'Artificial Intelligence' -> 'artificial-intelligence'. "
            "Example: 'Python Programming' -> 'python'. "
            "Example: 'The future of Web3' -> 'web3'."
        )
        tag = await self.llm.generate_response(prompt)
        # Clean up in case the LLM ignored instructions
        tag = tag.strip().lower().replace(" ", "-")
        import re
        tag = re.sub(r'[^a-z0-9\-]', '', tag)
        return tag if tag else "technology"

    async def get_curated_content(self, source: str, instruction: str) -> str:
        """Generates a curated content digest or article summary based on an instruction."""
        prompt = (
            f"You are a Tech Content Curator. Source category: {source}.\n"
            f"Instruction: {instruction}\n\n"
            "Rewrite the content into a friendly, structured WhatsApp reading list. "
            "CRITICAL WHATSAPP FORMATTING RULES:\n"
            "1. WhatsApp DOES NOT support markdown links like [text](url). You MUST output the raw URL directly (e.g. 'Read more: https://...').\n"
            "2. Use *asterisks* for bold text, not double asterisks.\n"
            "3. Use _underscores_ for italics."
        )
        
        content = await self.llm.generate_response(prompt)
        self.history.add_to_history(f"curated:{source}", content[:50])
        return content
