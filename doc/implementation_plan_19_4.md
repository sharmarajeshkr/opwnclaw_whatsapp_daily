# Implementation Plan: Test Suite Refactoring and Verification

This plan outlines the steps required to restore the test suite and verify the integrity of the Interview platform following the major architectural restructuring (migration from `src/` to `app/`).

## User Review Required

> [!IMPORTANT]
> Some tests linked to the monolithic `InterviewAgent` logic (like `test_agent_eval.py`) will be refactored to target the new specialized agents (`ScoringAgent`, `DeepDiveAgent`, etc.). The behavior will remain consistent with the original requirements. I will maintain a single `test_agent_eval.py` but update it to test the relevant methods across the new specialized agents.


## Proposed Changes

### 1. Robust Parsing Utility
Move the regex-based block extraction and JSON parsing logic from the old `InterviewAgent` into a centralized utility to ensure consistency across all new specialized agents.

#### [NEW] [utils.py](file:///c:/openClaw/app/agents/utils.py)
- `_extract_block(text, tag)`: Robustly extract content between [TAG] markers.
- `_parse_eval_response(raw, topic)`: Safely parse JSON from LLM responses with fallback.

### 2. Specialized Agents Refinement
Update the newly created agents to use the robust parsing utilities instead of simplified logic.

#### [MODIFY] [scoring_agent.py](file:///c:/openClaw/app/agents/scoring_agent.py)
#### [MODIFY] [deep_dive_agent.py](file:///c:/openClaw/app/agents/deep_dive_agent.py)
#### [MODIFY] [news_agent.py](file:///c:/openClaw/app/agents/news_agent.py)

### 3. Test Suite Refactoring
Update all import statements and package references in the `tests/` directory.

#### [MODIFY] [conftest.py](file:///c:/openClaw/tests/conftest.py)
#### [MODIFY] [test_config.py](file:///c:/openClaw/tests/test_config.py)
#### [MODIFY] [test_db.py](file:///c:/openClaw/tests/test_db.py)
#### [MODIFY] [test_performance.py](file:///c:/openClaw/tests/test_performance.py)
#### [MODIFY] [test_session.py](file:///c:/openClaw/tests/test_session.py)
#### [MODIFY] [test_delivery.py](file:///c:/openClaw/tests/test_delivery.py)
#### [MODIFY] [test_build_jid.py](file:///c:/openClaw/tests/test_build_jid.py)
#### [MODIFY] [test_agent_eval.py](file:///c:/openClaw/tests/test_agent_eval.py)
- Refactor to target `ScoringAgent` and `DeepDiveAgent`.
#### [MODIFY] [test_integration_coach_loop.py](file:///c:/openClaw/tests/test_integration_coach_loop.py)
- Refactor to use `InterviewScheduler`.


## Verification Plan

### Automated Tests
- Run the entire suite using `python -m pytest`.
- Target: 100% pass rate for all migrated functionality.

### Manual Verification
- Verify that LLM logs show correct parsing of JSON blocks during test execution.
- Ensure the `logs/` directory is correctly populated during test runs.
