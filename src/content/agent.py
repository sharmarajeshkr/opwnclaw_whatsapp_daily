import os
import json
import re
from src.content.llm import LLMProvider
from src.content.history import UserHistoryManager
from src.core.logger import get_logger

logger = get_logger("InterviewAgent")

class InterviewAgent:
    def __init__(self, phone_number: str, topic: str = "Software Engineering"):
        self.llm = LLMProvider()
        self.history_manager = UserHistoryManager(phone_number)
        self.topic = topic

    async def get_daily_challenge(self) -> tuple[str, str]:
        """Returns (detailed_text, image_prompt) for the daily challenge, avoiding history."""
        history = self.history_manager.get_history("challenges")
        history_str = "\n".join([f"- {h}" for h in history])
        
        prompt = f"""
        Generate a high-quality HLD/LLD Architecture Challenge and a DEEP-DIVE Solution for a Senior Architect role.
        
        Topics: Kafka, Spring Boot, microservices, Distributed Tracing, Circuit Breaker, API Gateway, caching, DB scaling, Python, ML, Agentic AI.
        
        PREVIOUS CHALLENGES TO AVOID:
        {history_str}
        
        Style Example: "Design a payment retry platform handling 10M events/day."
        
        The Solution MUST be extremely detailed and cover:
        1. *High-Level Design (HLD)* - Component interaction, data flow, throughput scaling.
        2. *Database Schema* - Exact tables, indexing strategies, data types (JSONB, partitions).
        3. *Event/Logic Flow* - Microservice coordination, Kafka topics, state transitions.
        4. *Reliability* - Retry + DLQ, Circuit Breakers, idempotency keys, fallout management.
        5. *Observability* - Distributed tracing (OpenTelemetry), key metrics, SLOs.
        
        Provide:
        - *Architectural Challenge* (The Problem).
        - *Proposed Solution* (Deep-dive sections 1-5).        
        
        Format the output for WhatsApp (use *bold* for headers and list items).
        """
        response = await self.llm.generate_response(prompt)
        
        # Add a snippet of the challenge to history
        first_line = response.split('\n', 1)[0].strip('*')[:200]
        self.history_manager.add_to_history("challenges", first_line)

        return response.strip(), "A professional technical architecture diagram of a high-scale distributed system."

    async def get_deep_dive_with_question(self, subject: str) -> tuple[str, str]:
        """
        Returns (scoreable_question, full_WhatsApp_message).

        The question is stored in SessionManager so the user's reply can be
        scored later. The full message (question + detailed answer) is what
        gets sent to WhatsApp.
        """
        history = self.history_manager.get_history(subject)
        history_str = "\n".join([f"- {h}" for h in history])

        prompt = f"""
        Generate a senior-level technical deep-dive focused entirely on '{subject}'.

        PREVIOUS TOPICS COVERED (DO NOT REPEAT):
        {history_str}

        Structure your response EXACTLY as follows (use these exact markers):

        [QUESTION]
        <A single complex, real-world scenario or conceptual question about {subject}.>
        [/QUESTION]

        [ANSWER]
        <A 500-800 word detailed explanation covering mechanics, trade-offs, and best practices.>
        [/ANSWER]

        Format the entire response for WhatsApp (use *bold* for headers and list items).
        """
        response = await self.llm.generate_response(prompt)

        # Parse the two sections
        question = self._extract_block(response, "QUESTION")
        answer = self._extract_block(response, "ANSWER")

        # Fallback: if markers not found, treat entire response as both
        if not question or not answer:
            logger.warning(f"[{subject}] Deep-dive markers not found — using full response.")
            question = response.split('\n', 1)[0].strip()
            answer = response.strip()

        full_message = f"*Question:*\n{question.strip()}\n\n*Answer:*\n{answer.strip()}"

        # Store snippet in send history to avoid repeats
        snippet = question[:200].strip('*')
        self.history_manager.add_to_history(subject, snippet)

        return question.strip(), full_message

    async def get_deep_dive(self, subject: str) -> str:
        """Legacy wrapper — returns the full WhatsApp message only."""
        _, full_message = await self.get_deep_dive_with_question(subject)
        return full_message

    # ------------------------------------------------------------------
    # Answer Evaluation
    # ------------------------------------------------------------------

    async def evaluate_answer(
        self, question: str, user_answer: str, topic: str
    ) -> dict:
        """
        Score a user's WhatsApp reply against the original question.

        Returns:
            {
              "score":        int (0–10),
              "feedback":     str (2–3 line WhatsApp-ready message),
              "weak_aspects": list[str]  (concepts the user missed)
            }
        If the LLM returns malformed JSON the method returns a safe fallback
        so the calling code never crashes.
        """
        prompt = f"""
        You are an expert senior engineering interviewer assessing a candidate's answer.

        TOPIC: {topic}

        QUESTION ASKED:
        {question}

        CANDIDATE'S ANSWER:
        {user_answer}

        Evaluate the answer and return ONLY valid JSON — no extra text, no markdown fences:
        {{"score": <integer 0-10>, "feedback": "<2-3 sentence WhatsApp-ready feedback>", "weak_aspects": ["<concept missed>", ...]}}

        Scoring guide:
        - 9-10: Exceptional — covers all key aspects with depth
        - 7-8:  Good — minor gaps or shallow on one area
        - 5-6:  Partial — important concepts missing
        - 3-4:  Weak — fundamental misunderstandings
        - 0-2:  Off-topic or no real attempt
        """
        raw = await self.llm.generate_response(prompt)
        return self._parse_eval_response(raw, topic)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_block(text: str, tag: str) -> str:
        """Extract content between [TAG] ... [/TAG] markers (case-insensitive)."""
        pattern = rf'\[{tag}\](.*?)\[/{tag}\]'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _parse_eval_response(raw: str, topic: str) -> dict:
        """Safely parse JSON from the LLM evaluation response."""
        try:
            # Strip any accidental markdown code fences
            cleaned = re.sub(r'```[\w]*', '', raw).strip()
            # Extract first JSON object found
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "score":        max(0, min(10, int(data.get("score", 5)))),
                    "feedback":     str(data.get("feedback", "Answer received!")),
                    "weak_aspects": list(data.get("weak_aspects", [])),
                }
        except Exception as exc:
            logger.warning(f"Could not parse eval JSON for topic '{topic}': {exc}")
        # Safe fallback — never crash the handler
        return {"score": 5, "feedback": "Answer received! Keep practising 💪", "weak_aspects": []}

    async def get_curated_content(self, category: str, raw_search_results: str) -> str:
        """Summarizes search results for a specific category while avoiding history."""
        history = self.history_manager.get_history(category)
        history_str = "\n".join([f"- {h}" for h in history])
        
        prompt = f"""
        Given the following raw research on '{category}', summarize it for a WhatsApp update.
        
        PREVIOUS {category.upper()} SENT (DO NOT REPEAT):
        {history_str}
        
        Provide:
        - 3-4 top entries, each with:
            - A concise *Title*.
            - A 500-1000 word *Summary*.
            - A *Read More* link (google search link for the topic).
        - Format for WhatsApp (use *bold* for headers and > for descriptions).
        - Be concise but informative.
        
        RESEARCH:
        {raw_search_results}
        """
        summary = await self.llm.generate_response(prompt)
        # Add some identifiers to history
        self.history_manager.add_to_history(category, summary[:500])
        return summary.strip()
