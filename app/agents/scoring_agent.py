"""
app/agents/scoring_agent.py
--------------------------
Specialized agent for evaluating user answers and providing scoring/feedback.
"""
import json
from app.llm.provider import LLMProvider
from app.core.logging import get_logger

from app.agents.utils import parse_eval_response
logger = get_logger("ScoringAgent")

class ScoringAgent:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.llm = LLMProvider()

    async def evaluate_answer(self, question: str, user_answer: str, topic: str, level: str) -> dict:
        """
        Evaluates a user's reply. 
        Acts as a mentor: if the user asks a question, it answers. 
        If it's an answer, it scores it.
        """
        prompt = (
            f"You are a Senior Technical Mentor. A student is in an interview for the topic '{topic}' at a {level} level.\n\n"
            f"CONTEXT:\n"
            f"Question asked to student: {question}\n"
            f"Student's reply: {user_answer}\n\n"
            "YOUR TASK:\n"
            "1. Detect if the student is providing an answer or asking a question/seeking clarification.\n"
            "2. If they are asking a question: Provide a **detailed and comprehensive technical mentorship response** in 'feedback'. "
            "Explain the concepts thoroughly, use simplified analogies where helpful, and provide architectural best practices. (Do NOT limit yourself to 3 sentences; provide value.) "
            "Set a 'follow_up_question' to guide them back to the original challenge.\n"
            "3. If they are providing an answer: Evaluate it technically. Provide **thorough feedback and critique** (feedback), a 'score' (0-10), and 'weak_aspects'. "
            "Set 'follow_up_question' to null unless you want to challenge them further with a deeper technical recursion.\n\n"
            "Return a JSON object with:\n"
            "1. 'score': Integer 0-10\n"
            "2. 'feedback': Your detailed technical response (WhatsApp markdown)\n"
            "3. 'weak_aspects': List of missed concepts (only if scoring an answer)\n"
            "4. 'is_correct': Boolean\n"
            "5. 'follow_up_question': A string containing a new follow-up question, or null if the session should end.\n"
        )
        
        response = await self.llm.generate_response(prompt)
        return parse_eval_response(response, topic)
