# -*- coding: utf-8 -*-
"""
tests/conftest.py
-----------------
Shared pytest configuration and fixtures.

- Ensures the project root is on sys.path so `src.*` imports resolve.
- Provides a session-scoped logging suppression to keep test output clean.
"""

import sys
import os
import logging
import pytest

# Add project root to path so `src.*` imports work from any working directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session", autouse=True)
def suppress_noisy_loggers():
    """
    Suppress verbose logger output during tests.
    Only WARNING and above will be shown, keeping test output clean.
    """
    for name in ["CoachDB", "SessionManager", "PerformanceTracker",
                  "InterviewAgent", "InterviewScheduler", "LLMProvider"]:
        logging.getLogger(name).setLevel(logging.WARNING)
