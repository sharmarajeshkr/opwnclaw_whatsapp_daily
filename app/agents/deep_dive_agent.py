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
        
        # Robust extraction
        question = extract_block(response, "QUESTION")
        answer = extract_block(response, "ANSWER")
        
        # Fallback: if markers not found, treat first line as question and full as content
        if not question or not answer:
            logger.warning(f"[{topic}] Deep-dive markers not found — using fallback slicing.")
            question = response.split('\n', 1)[0].strip()
            full_content = response.strip()
        else:
            full_content = f"*Question:*\n{question}\n\n*Answer:*\n{answer}"
        
        self.history.add_to_history(f"deep_dive:{topic}", question[:200])
        return question.strip(), full_content
