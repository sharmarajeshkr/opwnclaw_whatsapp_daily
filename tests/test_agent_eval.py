# -*- coding: utf-8 -*-
"""
tests/test_agent_eval.py
-------------------------
Tests for InterviewAgent.evaluate_answer() and _parse_eval_response()

Covers:
  - Valid JSON response parsed correctly
  - Score clamped to [0, 10]
  - Missing keys fall back to defaults
  - Malformed JSON returns safe fallback (never raises)
  - Markdown code fences stripped from LLM output
  - Empty weak_aspects returned as empty list
  - LLM call is mocked — no real API calls
  - get_deep_dive_with_question returns (question, full_message) tuple
  - [QUESTION]/[ANSWER] block extraction
  - Fallback when markers missing
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_agent(llm_response: str):
    """Create an InterviewAgent with a mocked LLM that returns llm_response."""
    with patch("src.content.agent.LLMProvider") as MockLLM, \
         patch("src.content.agent.UserHistoryManager") as MockHist:
        MockLLM.return_value.generate_response = AsyncMock(return_value=llm_response)
        MockLLM.return_value.generate_image = AsyncMock(return_value="")
        MockHist.return_value.get_history = MagicMock(return_value=[])
        MockHist.return_value.add_to_history = MagicMock()

        from src.content.agent import InterviewAgent
        agent = InterviewAgent(phone_number="919999999999")
        # Patch the already-constructed llm inside agent
        agent.llm.generate_response = AsyncMock(return_value=llm_response)
        agent.history_manager.get_history = MagicMock(return_value=[])
        agent.history_manager.add_to_history = MagicMock()
        return agent


# ── _parse_eval_response (static method — unit-testable directly) ───────────────

class TestParseEvalResponse:
    def _parse(self, raw):
        from src.content.agent import InterviewAgent
        return InterviewAgent._parse_eval_response(raw, "Kafka")

    def test_valid_json_parsed(self):
        raw = '{"score": 7, "feedback": "Good effort!", "weak_aspects": ["DLQ"]}'
        result = self._parse(raw)
        assert result["score"] == 7
        assert result["feedback"] == "Good effort!"
        assert result["weak_aspects"] == ["DLQ"]

    def test_score_clamped_above_10(self):
        raw = '{"score": 15, "feedback": "Great!", "weak_aspects": []}'
        result = self._parse(raw)
        assert result["score"] == 10

    def test_score_clamped_below_0(self):
        raw = '{"score": -5, "feedback": "Try harder.", "weak_aspects": []}'
        result = self._parse(raw)
        assert result["score"] == 0

    def test_missing_score_defaults_to_5(self):
        raw = '{"feedback": "Ok.", "weak_aspects": []}'
        result = self._parse(raw)
        assert result["score"] == 5

    def test_missing_feedback_defaults(self):
        raw = '{"score": 6, "weak_aspects": []}'
        result = self._parse(raw)
        assert isinstance(result["feedback"], str)
        assert len(result["feedback"]) > 0

    def test_missing_weak_aspects_defaults_to_empty_list(self):
        raw = '{"score": 6, "feedback": "Decent."}'
        result = self._parse(raw)
        assert result["weak_aspects"] == []

    def test_empty_weak_aspects(self):
        raw = '{"score": 9, "feedback": "Excellent!", "weak_aspects": []}'
        result = self._parse(raw)
        assert result["weak_aspects"] == []

    def test_multiple_weak_aspects(self):
        raw = '{"score": 4, "feedback": "Needs work.", "weak_aspects": ["DLQ", "idempotency", "retry"]}'
        result = self._parse(raw)
        assert len(result["weak_aspects"]) == 3

    def test_markdown_code_fence_stripped(self):
        """LLMs sometimes wrap JSON in ```json ... ```"""
        raw = '```json\n{"score": 8, "feedback": "Nice!", "weak_aspects": []}\n```'
        result = self._parse(raw)
        assert result["score"] == 8

    def test_extra_text_before_json(self):
        """LLM sometimes adds commentary before the JSON block."""
        raw = 'Here is my evaluation:\n{"score": 6, "feedback": "Ok.", "weak_aspects": ["timeout"]}'
        result = self._parse(raw)
        assert result["score"] == 6

    def test_completely_malformed_returns_fallback(self):
        raw = "I cannot evaluate this answer."
        result = self._parse(raw)
        # Should return safe fallback without raising
        assert isinstance(result["score"], int)
        assert isinstance(result["feedback"], str)
        assert isinstance(result["weak_aspects"], list)

    def test_empty_string_returns_fallback(self):
        result = self._parse("")
        assert result["score"] == 5


# ── _extract_block (static method) ────────────────────────────────────────────

class TestExtractBlock:
    def _extract(self, text, tag):
        from src.content.agent import InterviewAgent
        return InterviewAgent._extract_block(text, tag)

    def test_extracts_question_block(self):
        text = "[QUESTION]\nWhat is Kafka?\n[/QUESTION]\n[ANSWER]\nKafka is...\n[/ANSWER]"
        assert self._extract(text, "QUESTION") == "What is Kafka?"

    def test_extracts_answer_block(self):
        text = "[QUESTION]\nQ?\n[/QUESTION]\n[ANSWER]\nDetailed answer here.\n[/ANSWER]"
        assert self._extract(text, "ANSWER") == "Detailed answer here."

    def test_case_insensitive(self):
        text = "[question]\nQ?\n[/question]"
        assert self._extract(text, "QUESTION") == "Q?"

    def test_returns_empty_when_marker_missing(self):
        text = "This response has no markers at all."
        assert self._extract(text, "QUESTION") == ""

    def test_multiline_extraction(self):
        text = "[QUESTION]\nLine 1\nLine 2\nLine 3\n[/QUESTION]"
        result = self._extract(text, "QUESTION")
        assert "Line 1" in result
        assert "Line 3" in result


# ── evaluate_answer (async — mocked LLM) ──────────────────────────────────────

class TestEvaluateAnswer:
    def run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_returns_dict_with_required_keys(self):
        payload = '{"score": 7, "feedback": "Good!", "weak_aspects": ["DLQ"]}'
        agent = make_agent(payload)
        result = self.run(agent.evaluate_answer("Q?", "My answer.", "Kafka"))
        assert "score" in result
        assert "feedback" in result
        assert "weak_aspects" in result

    def test_score_is_int(self):
        payload = '{"score": 8, "feedback": "Nice!", "weak_aspects": []}'
        agent = make_agent(payload)
        result = self.run(agent.evaluate_answer("Q?", "ans", "Redis"))
        assert isinstance(result["score"], int)

    def test_weak_aspects_is_list(self):
        payload = '{"score": 4, "feedback": "Work harder.", "weak_aspects": ["timeout", "retry"]}'
        agent = make_agent(payload)
        result = self.run(agent.evaluate_answer("Q?", "ans", "Kafka"))
        assert isinstance(result["weak_aspects"], list)

    def test_malformed_llm_doesnt_raise(self):
        """If LLM returns garbage, evaluate_answer must return a safe fallback."""
        agent = make_agent("I cannot answer this.")
        result = self.run(agent.evaluate_answer("Q?", "ans", "Kafka"))
        assert isinstance(result, dict)
        assert "score" in result

    def test_score_within_bounds(self):
        """Score should always be in [0, 10] regardless of LLM output."""
        payload = '{"score": 99, "feedback": "Amazing!", "weak_aspects": []}'
        agent = make_agent(payload)
        result = self.run(agent.evaluate_answer("Q?", "ans", "Kafka"))
        assert 0 <= result["score"] <= 10


# ── get_deep_dive_with_question (async — mocked LLM) ──────────────────────────

class TestGetDeepDiveWithQuestion:
    def run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _make_agent_with_response(self, response: str):
        return make_agent(response)

    def test_returns_tuple_of_two_strings(self):
        response = "[QUESTION]\nWhat is Kafka?\n[/QUESTION]\n[ANSWER]\nKafka is a distributed log.\n[/ANSWER]"
        agent = self._make_agent_with_response(response)
        result = self.run(agent.get_deep_dive_with_question("Kafka"))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_question(self):
        response = "[QUESTION]\nExplain consumer groups.\n[/QUESTION]\n[ANSWER]\nLong answer.\n[/ANSWER]"
        agent = self._make_agent_with_response(response)
        question, _ = self.run(agent.get_deep_dive_with_question("Kafka"))
        assert "consumer groups" in question.lower()

    def test_second_element_contains_both_parts(self):
        response = "[QUESTION]\nQuestion here.\n[/QUESTION]\n[ANSWER]\nAnswer here.\n[/ANSWER]"
        agent = self._make_agent_with_response(response)
        _, full_msg = self.run(agent.get_deep_dive_with_question("Kafka"))
        assert "Question here" in full_msg
        assert "Answer here" in full_msg

    def test_fallback_when_no_markers(self):
        """If LLM doesn't use markers, it should not crash."""
        response = "This is an unstructured response without any markers."
        agent = self._make_agent_with_response(response)
        question, full_msg = self.run(agent.get_deep_dive_with_question("Kafka"))
        # Should not raise, and both should be non-empty strings
        assert isinstance(question, str)
        assert isinstance(full_msg, str)

    def test_history_manager_called(self):
        response = "[QUESTION]\nQ?\n[/QUESTION]\n[ANSWER]\nA.\n[/ANSWER]"
        agent = self._make_agent_with_response(response)
        self.run(agent.get_deep_dive_with_question("Kafka"))
        agent.history_manager.add_to_history.assert_called_once()

    def test_get_deep_dive_legacy_wrapper_returns_string(self):
        """get_deep_dive() is a legacy wrapper — must still return a string."""
        response = "[QUESTION]\nQ?\n[/QUESTION]\n[ANSWER]\nA.\n[/ANSWER]"
        agent = self._make_agent_with_response(response)
        result = self.run(agent.get_deep_dive("Kafka"))
        assert isinstance(result, str)
