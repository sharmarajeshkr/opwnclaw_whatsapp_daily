"""
app/agents/coding_agent.py
--------------------------
Specialized agent for generating daily coding exercises with complete
solutions in both Python and Java. Exercises vary by difficulty level
and target common interview patterns (arrays, trees, DP, graphs, etc.).
"""

from app.llm.provider import LLMProvider
from app.database.history import UserHistoryManager
from app.core.logging import get_logger

logger = get_logger("CodingAgent")


class CodingAgent:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.llm = LLMProvider()
        self.history = UserHistoryManager(phone_number)

    async def get_daily_exercise(self, level: str = "Intermediate", week: int = 1) -> str:
        """
        Generates a unique daily coding problem with full Python and Java solutions.
        Returns formatted WhatsApp-ready text.
        """
        # Build a rotation hint so problems don't repeat
        categories = [
            "Arrays & Hashing",
            "Two Pointers",
            "Sliding Window",
            "Binary Search",
            "Linked Lists",
            "Trees & BST",
            "Graphs & BFS/DFS",
            "Dynamic Programming",
            "Recursion & Backtracking",
            "Sorting & Searching",
            "Heaps & Priority Queues",
            "Tries & String Manipulation",
            "Bit Manipulation",
            "Greedy Algorithms",
            "Math & Number Theory",
        ]
        category = categories[(week - 1) % len(categories)]

        prompt = (
            f"You are a world-class coding interview coach. Generate a FRESH daily coding exercise.\n\n"
            f"Constraints:\n"
            f"- Difficulty: {level}\n"
            f"- Category: {category} (Week {week})\n"
            f"- The problem must be UNIQUE — do NOT repeat classic overused problems like Two Sum or FizzBuzz.\n\n"
            f"Output Format (strictly follow this for WhatsApp — NO markdown links, use *bold* for headings):\n\n"
            f"💻 *Daily Coding Challenge — {category}*\n"
            f"📊 Difficulty: {level} | Week {week}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*📝 Problem Statement*\n"
            f"[Clear, concise problem description in 3-5 sentences]\n\n"
            f"*📥 Input / Output*\n"
            f"Example 1:\n"
            f"  Input: [provide example]\n"
            f"  Output: [provide expected output]\n"
            f"  Explanation: [short explanation]\n\n"
            f"*💡 Constraints*\n"
            f"[List 2-3 key constraints, e.g. 1 ≤ n ≤ 10⁵]\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*🐍 Python Solution*\n"
            f"[Complete, runnable Python solution with inline comments]\n\n"
            f"*☕ Java Solution*\n"
            f"[Complete, runnable Java solution with inline comments]\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*⏱ Complexity*\n"
            f"Time: O(?)\n"
            f"Space: O(?)\n\n"
            f"*🔑 Key Insight*\n"
            f"[One-sentence explanation of the core algorithmic trick]\n\n"
            f"_Try solving it first before looking at the solution! 💪_"
        )

        content = await self.llm.generate_response(prompt)
        self.history.add_to_history("coding_exercise", content[:80])
        return content
