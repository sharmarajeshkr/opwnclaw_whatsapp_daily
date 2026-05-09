"""
app/llm/backend_selector.py
----------------------------
NEW FILE — Central backend selector for the LLM infrastructure.

Reads LLM_BACKEND from .env and returns the correct Scheduler class.
This is the ONLY place in the codebase where the Ollama vs Cloud decision
is made. No existing files are modified to support this.

Supported values for LLM_BACKEND in .env:
    openai   → uses original InterviewScheduler  (OpenAI / Gemini cloud)
    ollama   → uses OllamaInterviewScheduler     (local Ollama models)

Usage (in main.py — one line replaces the old static import):
    from app.llm.backend_selector import get_scheduler_class
    SchedulerClass = get_scheduler_class()
    scheduler = SchedulerClass(whatsapp, phone_number)
"""
import os
from app.core.logging import get_logger

# Load .env so os.getenv() picks up LLM_BACKEND even when called before
# pydantic-settings has initialised (e.g. during import resolution).
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)   # override=False: real env vars always win
except ImportError:
    pass  # python-dotenv not installed — rely on shell environment

logger = get_logger("BackendSelector")

# ── Supported backends ─────────────────────────────────────────────────────
_OPENAI_BACKEND  = "openai"
_OLLAMA_BACKEND  = "ollama"
_VALID_BACKENDS  = {_OPENAI_BACKEND, _OLLAMA_BACKEND}

# ── Env-var name ────────────────────────────────────────────────────────────
_ENV_KEY = "LLM_BACKEND"


def get_active_backend() -> str:
    """
    Returns the active backend name from the LLM_BACKEND env variable.
    Defaults to 'openai' if not set or unrecognised.
    """
    raw = os.getenv(_ENV_KEY, _OPENAI_BACKEND).strip().lower()
    if raw not in _VALID_BACKENDS:
        logger.warning(
            f"Unknown LLM_BACKEND='{raw}'. "
            f"Valid options: {_VALID_BACKENDS}. Defaulting to '{_OPENAI_BACKEND}'."
        )
        return _OPENAI_BACKEND
    return raw


def get_scheduler_class():
    """
    Returns the correct InterviewScheduler class based on LLM_BACKEND.

    Returns:
        InterviewScheduler        — if LLM_BACKEND=openai  (or unset)
        OllamaInterviewScheduler  — if LLM_BACKEND=ollama
    """
    backend = get_active_backend()

    if backend == _OLLAMA_BACKEND:
        logger.info("LLM_BACKEND=ollama  — Loading OllamaInterviewScheduler (local models).")
        from app.services.ollama_scheduler import OllamaInterviewScheduler
        return OllamaInterviewScheduler

    # Default: cloud provider (OpenAI / Gemini)
    logger.info("LLM_BACKEND=openai  — Loading InterviewScheduler (cloud provider).")
    from app.services.scheduler import InterviewScheduler
    return InterviewScheduler


def is_ollama_mode() -> bool:
    """Convenience helper — True when running in Ollama mode."""
    return get_active_backend() == _OLLAMA_BACKEND


def is_openai_mode() -> bool:
    """Convenience helper — True when running in cloud/OpenAI mode."""
    return get_active_backend() == _OPENAI_BACKEND
