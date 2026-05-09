"""
app/agents/ollama/ollama_agents.py
----------------------------------
NEW FILE — Ollama-backed versions of every existing agent.

Each class is a thin subclass that swaps self.llm for an OllamaProvider
instance. Zero changes to original agent files.

Example usage in ollama_scheduler.py:
    from app.agents.ollama.ollama_agents import (
        OllamaInterviewAgent,
        OllamaCodingAgent,
        OllamaDeepDiveAgent,
        OllamaCuratorAgent,
        OllamaScoringAgent,
    )
"""
from app.agents.interview_agent import InterviewAgent
from app.agents.coding_agent import CodingAgent
from app.agents.deep_dive_agent import DeepDiveAgent
from app.agents.curator_agent import CuratorAgent
from app.agents.scoring_agent import ScoringAgent
from app.llm.ollama_provider import OllamaProvider
from app.core.logging import get_logger

logger = get_logger("OllamaAgents")


# ---------------------------------------------------------------------------
# Helper — swap the llm on any agent instance
# ---------------------------------------------------------------------------

def _patch_llm(agent, model: str):
    """Replace agent.llm with an OllamaProvider in-place."""
    agent.llm = OllamaProvider(model=model)
    logger.info(f"{agent.__class__.__name__} patched to use ollama/{model}")
    return agent


# ---------------------------------------------------------------------------
# Ollama-backed agent classes
# ---------------------------------------------------------------------------

class OllamaInterviewAgent(InterviewAgent):
    """
    Architecture challenge agent powered by a local Ollama model.
    Recommended model: llama3.1:8b
    """
    def __init__(self, phone_number: str, model: str = "llama3.1:8b"):
        super().__init__(phone_number)
        _patch_llm(self, model)


class OllamaDeepDiveAgent(DeepDiveAgent):
    """
    Deep-dive technical mentor powered by a local Ollama model.
    Recommended model: llama3.1:8b
    """
    def __init__(self, phone_number: str, model: str = "llama3.1:8b"):
        super().__init__(phone_number)
        _patch_llm(self, model)


class OllamaCodingAgent(CodingAgent):
    """
    Daily coding exercise agent powered by a local Ollama model.
    Recommended model: qwen2.5-coder:7b or codellama
    """
    def __init__(self, phone_number: str, model: str = "qwen2.5-coder:7b"):
        super().__init__(phone_number)
        _patch_llm(self, model)


class OllamaCuratorAgent(CuratorAgent):
    """
    Tech news curator powered by a local Ollama model.
    Recommended model: phi3:mini or llama3.1:8b
    """
    def __init__(self, phone_number: str, model: str = "phi3:mini"):
        super().__init__(phone_number)
        _patch_llm(self, model)


class OllamaScoringAgent(ScoringAgent):
    """
    Answer evaluation agent powered by a local Ollama model.
    NOTE: Cloud models (GPT-4o-mini, Gemini) typically give more accurate
    scoring. Use this only if you want a fully offline setup.
    Recommended model: llama3.1:8b
    """
    def __init__(self, phone_number: str, model: str = "llama3.1:8b"):
        super().__init__(phone_number)
        _patch_llm(self, model)
