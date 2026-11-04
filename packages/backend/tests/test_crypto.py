from __future__ import annotations

import pytest

from app.security import crypto


def test_roundtrip_preserves_plaintext():
    token = crypto.encrypt("sk-prod-ABCDEFGHIJKL")
    assert token != "sk-prod-ABCDEFGHIJKL"
    assert crypto.decrypt(token) == "sk-prod-ABCDEFGHIJKL"


def test_invalid_token_rejected():
    with pytest.raises(crypto.CryptoDecryptionError):
        crypto.decrypt("this-is-not-a-fernet-token")


def test_empty_token_rejected():
    with pytest.raises(crypto.CryptoDecryptionError):
        crypto.decrypt("")


def test_cross_secret_token_rejected(monkeypatch):
    token = crypto.encrypt("hello")
    monkeypatch.setenv(
        "MASTER_KEY_SECRET",
        "entirely-different-master-secret-key-material-xx",
    )
    crypto.reset_cache_for_tests()
    with pytest.raises(crypto.CryptoDecryptionError):
        crypto.decrypt(token)


def test_mask_long():
    assert crypto.mask("sk-1234567890ab") == "sk-...ab"


def test_mask_short_or_eight():
    assert crypto.mask("short") == "***"
    assert crypto.mask("12345678") == "***"


def test_mask_nonstring():
    assert crypto.mask(None) == "***"  # type: ignore[arg-type]


def test_missing_master_secret(monkeypatch):
    monkeypatch.delenv("MASTER_KEY_SECRET", raising=False)
    crypto.reset_cache_for_tests()
    with pytest.raises(crypto.CryptoConfigError):
        crypto.encrypt("x")


def test_short_master_secret_rejected(monkeypatch):
    monkeypatch.setenv("MASTER_KEY_SECRET", "tiny")
    crypto.reset_cache_for_tests()
    with pytest.raises(crypto.CryptoConfigError):
        crypto.encrypt("x")
