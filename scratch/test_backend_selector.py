"""
scratch/test_backend_selector.py
---------------------------------
Tests that:
1. The backend selector correctly reads LLM_BACKEND from .env
2. It returns OllamaInterviewScheduler when LLM_BACKEND=ollama
3. It returns InterviewScheduler when LLM_BACKEND=openai
4. Makes a real LLM call using the selected backend to confirm end-to-end wiring
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import asyncio

# ── Test 1: Backend detection ────────────────────────────────────────────────
from app.llm.backend_selector import get_active_backend, get_scheduler_class, is_ollama_mode

backend = get_active_backend()
SchedulerClass = get_scheduler_class()

print("=" * 55)
print("  OpenClaw — Backend Selector Test")
print("=" * 55)
print(f"  LLM_BACKEND env value : '{backend}'")
print(f"  is_ollama_mode()      : {is_ollama_mode()}")
print(f"  Scheduler class       : {SchedulerClass.__name__}")
print()

# ── Test 2: Correct class selected? ─────────────────────────────────────────
from app.services.scheduler import InterviewScheduler
from app.services.ollama_scheduler import OllamaInterviewScheduler

if backend == "ollama":
    expected = OllamaInterviewScheduler
    other    = InterviewScheduler
else:
    expected = InterviewScheduler
    other    = OllamaInterviewScheduler

if SchedulerClass is expected:
    print(f"  [PASS] Correct scheduler selected: {expected.__name__}")
else:
    print(f"  [FAIL] Wrong scheduler! Got {SchedulerClass.__name__}, expected {expected.__name__}")
    sys.exit(1)

# ── Test 3: Live LLM call via selected backend ───────────────────────────────
print()
print("-" * 55)
print(f"  Live LLM call via: {backend.upper()}")
print("-" * 55)

async def test_llm():
    if backend == "ollama":
        from app.llm.ollama_provider import OllamaProvider
        # Use whichever model is registered for slot 1 (default llama3.1:8b)
        from app.services.ollama_scheduler import OLLAMA_TOPIC_MODELS
        model = OLLAMA_TOPIC_MODELS.get(1, "llama3.1:8b")
        print(f"  Ollama model         : {model}")
        llm = OllamaProvider(model=model)
    else:
        from app.llm.provider import LLMProvider
        llm = LLMProvider()
        print(f"  Cloud model          : {llm.provider} / {llm.model_name}")

    prompt = "Respond with exactly: 'Backend OK'. Nothing else."
    try:
        response = await llm.generate_response(prompt)
        print(f"  Response             : {response.strip()}")
        print()
        print("  [PASS] End-to-end LLM call succeeded!")
    except Exception as e:
        print(f"  [FAIL] LLM call failed: {e}")

asyncio.run(test_llm())
print("=" * 55)
