"""
scratch/test_e2e_ollama.py
--------------------------
End-to-end test for the full Ollama pipeline:
  Layer 1  — backend_selector reads LLM_BACKEND=ollama from .env
  Layer 2  — OllamaProvider talks to local Ollama server
  Layer 3  — Ollama-backed agents (phi3:mini / qwen2.5-coder:7b) produce real output
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import asyncio

PASS = "[PASS]"
FAIL = "[FAIL]"
SEP  = "=" * 60

# ── Layer 1: Backend Selector ────────────────────────────────────────────────
print(SEP)
print("  OpenClaw -- End-to-End Ollama Test")
print(SEP)

from app.llm.backend_selector import get_active_backend, get_scheduler_class, is_ollama_mode

backend = get_active_backend()
print(f"\nLayer 1 -- Backend Selector")
print(f"  LLM_BACKEND       : {backend}")
print(f"  is_ollama_mode()  : {is_ollama_mode()}")
print(f"  Scheduler         : {get_scheduler_class().__name__}")

assert backend == "ollama", f"Expected 'ollama', got '{backend}'"
assert is_ollama_mode(), "is_ollama_mode() should be True"
print(f"  {PASS} Backend selector is correctly set to OLLAMA")

# ── Layer 2: OllamaProvider — raw model calls ────────────────────────────────
print(f"\nLayer 2 -- OllamaProvider (raw model calls)")

from app.llm.ollama_provider import OllamaProvider

async def test_provider():
    results = {}

    # Test phi3:mini
    print(f"\n  Testing phi3:mini ...")
    try:
        p = OllamaProvider(model="phi3:mini")
        resp = await p.generate_response("Reply with exactly: 'phi3 OK'. Nothing else.")
        print(f"  Raw response : {resp.strip()[:80]}")
        results["phi3:mini"] = True
        print(f"  {PASS} phi3:mini responded successfully")
    except Exception as e:
        print(f"  {FAIL} phi3:mini failed: {e}")
        results["phi3:mini"] = False

    # Test qwen2.5-coder:7b
    print(f"\n  Testing qwen2.5-coder:7b ...")
    try:
        q = OllamaProvider(model="qwen2.5-coder:7b")
        resp = await q.generate_response("Reply with exactly: 'qwen OK'. Nothing else.")
        print(f"  Raw response : {resp.strip()[:80]}")
        results["qwen2.5-coder:7b"] = True
        print(f"  {PASS} qwen2.5-coder:7b responded successfully")
    except Exception as e:
        print(f"  {FAIL} qwen2.5-coder:7b failed: {e}")
        results["qwen2.5-coder:7b"] = False

    return results

provider_results = asyncio.run(test_provider())

# ── Layer 3: Ollama-backed Agents ────────────────────────────────────────────
print(f"\nLayer 3 -- Ollama-backed Agents (real prompts)")

PHONE = "test_e2e"

from app.agents.ollama.ollama_agents import (
    OllamaInterviewAgent,
    OllamaCodingAgent,
    OllamaCuratorAgent,
    OllamaDeepDiveAgent,
)

async def test_agents():
    results = {}

    # --- Interview Agent (phi3:mini) ---
    print(f"\n  [1/3] InterviewAgent via phi3:mini ...")
    try:
        agent = OllamaInterviewAgent(PHONE, model="phi3:mini")
        text, _ = await agent.get_daily_challenge(
            level="Beginner", week=1, skill_profile={"backend": 5}
        )
        preview = text.strip()[:120].replace("\n", " ")
        print(f"  Preview : {preview}...")
        results["interview"] = True
        print(f"  {PASS} InterviewAgent produced content")
    except Exception as e:
        print(f"  {FAIL} InterviewAgent: {e}")
        results["interview"] = False

    # --- Curator Agent (phi3:mini) ---
    print(f"\n  [2/3] CuratorAgent via phi3:mini ...")
    try:
        agent = OllamaCuratorAgent(PHONE, model="phi3:mini")
        content = await agent.get_curated_content(
            "Tech_news", "Summarise the top 3 trends in AI for 2025 in 3 bullet points."
        )
        preview = content.strip()[:120].replace("\n", " ")
        print(f"  Preview : {preview}...")
        results["curator"] = True
        print(f"  {PASS} CuratorAgent produced content")
    except Exception as e:
        print(f"  {FAIL} CuratorAgent: {e}")
        results["curator"] = False

    # --- Coding Agent (qwen2.5-coder:7b) ---
    print(f"\n  [3/3] CodingAgent via qwen2.5-coder:7b ...")
    try:
        agent = OllamaCodingAgent(PHONE, model="qwen2.5-coder:7b")
        content = await agent.get_daily_exercise(level="Beginner", week=1)
        preview = content.strip()[:120].replace("\n", " ")
        print(f"  Preview : {preview}...")
        results["coding"] = True
        print(f"  {PASS} CodingAgent produced content")
    except Exception as e:
        print(f"  {FAIL} CodingAgent: {e}")
        results["coding"] = False

    return results

agent_results = asyncio.run(test_agents())

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  SUMMARY")
print(SEP)
all_results = {**provider_results, **agent_results}
total  = len(all_results)
passed = sum(1 for v in all_results.values() if v)

for name, ok in all_results.items():
    status = PASS if ok else FAIL
    print(f"  {status}  {name}")

print(f"\n  Score: {passed}/{total} tests passed")
if passed == total:
    print("  ALL TESTS PASSED -- Ollama is fully wired into the project!")
else:
    print("  Some tests failed -- check model availability with `ollama list`")
print(SEP)
