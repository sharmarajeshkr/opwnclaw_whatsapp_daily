# -*- coding: utf-8 -*-
"""
tests/conftest.py
-----------------
Shared pytest configuration and fixtures.

Ensures the project root is on sys.path so `app.*` imports resolve.
Provides session-scoped logging suppression to keep test output clean.
"""

import sys
import os
import logging
import pytest

# Add project root to path so `app.*` imports work
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

@pytest.fixture(scope="session", autouse=True)
def suppress_noisy_loggers():
    """
    Suppress verbose logger output during tests.
    Only WARNING and above will be shown, keeping test output clean.
    """
    noisy_loggers = [
        "CoachDB", "SessionManager", "PerformanceTracker", "LLMCache",
        "InterviewAgent", "ScoringAgent", "DeepDiveAgent", "NewsAgent",
        "InterviewScheduler", "LLMProvider", "AgentUtils",
        "WhatsAppClient", "WhatsAppHandler", "StreamlitApp", "Utils"
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)
