"""Test harness for the Slidoxa-owned security + migrations tests.

Adds packages/backend/ to sys.path so ``app.security.*`` imports
without a package install, and seeds deterministic test secrets.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_BACKEND_ROOT = _HERE.parent.parent  # packages/backend
sys.path.insert(0, str(_BACKEND_ROOT))


@pytest.fixture(autouse=True)
def _slidoxa_env(monkeypatch):
    # Deterministic test values; never reused outside tests.
    monkeypatch.setenv(
        "MASTER_KEY_SECRET",
        "test-master-secret-with-sufficient-entropy-0123456789",
    )
    monkeypatch.setenv(
        "JWT_SECRET",
        "test-jwt-secret-with-at-least-32-bytes-of-entropy-aaaaaa",
    )
    monkeypatch.setenv("COOKIE_SECURE", "false")
    # Force crypto cache re-derivation per test.
    from app.security import crypto
    crypto.reset_cache_for_tests()
    yield
    crypto.reset_cache_for_tests()
