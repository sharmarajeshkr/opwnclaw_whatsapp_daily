"""
app/services/ollama_scheduler.py
---------------------------------
NEW FILE — An Ollama-aware version of InterviewScheduler.

This subclass overrides ONLY _make_topic_task() to use the Ollama-backed
agent variants (from app/agents/ollama/ollama_agents.py) for the topic
slots you configure below.

The original app/services/scheduler.py is NOT modified at all.
All other scheduler behaviour (weekly reports, config watch, anti-spam,
session management) is inherited unchanged.

HOW TO USE:
-----------
In main.py (or wherever you instantiate the scheduler), change:

    # Before (original — uses cloud LLM):
    from app.services.scheduler import InterviewScheduler
    scheduler = InterviewScheduler(whatsapp, phone_number)

    # After (Ollama-aware — uses local models for configured slots):
    from app.services.ollama_scheduler import OllamaInterviewScheduler
    scheduler = OllamaInterviewScheduler(whatsapp, phone_number)

TOPIC → MODEL MAPPING:
-----------------------
Edit OLLAMA_TOPIC_MODELS below to choose which model each slot uses.
Set a slot to None to keep that slot using the original cloud provider.

  slot 1 = Architecture Challenge     → llama3.1:8b
  slot 2 = Deep Dive topic 2          → llama3.1:8b
  slot 3 = Deep Dive topic 3          → llama3.1:8b
  slot 4 = Fresh Updates / News       → phi3:mini
  slot 5 = Medium RSS curation        → phi3:mini
  slot 6 = Daily Coding Exercise      → qwen2.5-coder:7b  (or codellama)
"""

import asyncio
from app.services.scheduler import InterviewScheduler
from app.agents.ollama.ollama_agents import (
    OllamaInterviewAgent,
    OllamaDeepDiveAgent,
    OllamaCodingAgent,
    OllamaCuratorAgent,
)
from app.channels.whatsapp.client import WhatsAppClient
from app.services.session_manager import SessionManager
from app.services.performance_tracker import PerformanceTracker
from app.mcp.client import run_medium_query
from app.core.logging import get_logger
from app.core.utils import ContextAdapter

logger = get_logger("OllamaInterviewScheduler")

# ── Model assignment per topic slot ─────────────────────────────────────────
# Confirmed installed models (run `ollama list` to verify):
#   phi3:mini          2.2 GB  — fast, good for summaries / news curation
#   qwen2.5-coder:7b   4.7 GB  — best open-source coding model in 7B class
#
# Set to None to keep that slot on the original cloud provider (OpenAI/Gemini).
OLLAMA_TOPIC_MODELS = {
    1: "phi3:mini",           # Architecture Challenge  (lightweight + smart)
    2: "phi3:mini",           # Deep Dive topic 2
    3: "phi3:mini",           # Deep Dive topic 3
    4: "phi3:mini",           # Fresh Updates / News    (fast summarisation)
    5: "phi3:mini",           # Medium RSS curation
    6: "qwen2.5-coder:7b",   # Daily Coding Exercise   (best coding model)
}
# ────────────────────────────────────────────────────────────────────────────


class OllamaInterviewScheduler(InterviewScheduler):
    """
    Drop-in replacement for InterviewScheduler that uses local Ollama models
    for the topic slots defined in OLLAMA_TOPIC_MODELS above.
    """

    def __init__(self, whatsapp: WhatsAppClient, phone_number: str):
        # Call the parent __init__ — this sets up all original agents
        super().__init__(whatsapp, phone_number)

        # Override only the agents for slots that have an Ollama model configured.
        # Slots with None keep using the original cloud-backed agents.
        if OLLAMA_TOPIC_MODELS.get(1):
            self.interview_agent = OllamaInterviewAgent(phone_number, model=OLLAMA_TOPIC_MODELS[1])

        if OLLAMA_TOPIC_MODELS.get(2) or OLLAMA_TOPIC_MODELS.get(3):
            deep_model = OLLAMA_TOPIC_MODELS.get(2) or OLLAMA_TOPIC_MODELS.get(3)
            self.deep_dive_agent = OllamaDeepDiveAgent(phone_number, model=deep_model)

        if OLLAMA_TOPIC_MODELS.get(4) or OLLAMA_TOPIC_MODELS.get(5):
            curator_model = OLLAMA_TOPIC_MODELS.get(4) or OLLAMA_TOPIC_MODELS.get(5)
            self.curator_agent = OllamaCuratorAgent(phone_number, model=curator_model)

        if OLLAMA_TOPIC_MODELS.get(6):
            self.coding_agent = OllamaCodingAgent(phone_number, model=OLLAMA_TOPIC_MODELS[6])

        self.logger = ContextAdapter(logger, {"phone": phone_number})
        self.logger.info(
            f"[{phone_number}] OllamaInterviewScheduler ready. "
            f"Ollama models: {OLLAMA_TOPIC_MODELS}"
        )
