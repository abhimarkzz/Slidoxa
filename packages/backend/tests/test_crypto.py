from __future__ import annotations

import pytest

from app.security import crypto


def test_fernet_roundtrip_supports_text_and_bytea_storage():
    plaintext = "sk-prod-ABCDEFGHIJKL"
    token = crypto.encrypt(plaintext)
    assert token != plaintext
    assert crypto.decrypt(token) == plaintext
    assert crypto.decrypt(token.encode("ascii")) == plaintext
    assert crypto.decrypt(memoryview(token.encode("ascii"))) == plaintext


def test_invalid_token_rejected():
    with pytest.raises(crypto.CryptoDecryptionError):
        crypto.decrypt("this-is-not-a-fernet-token")


def test_empty_token_rejected():
    with pytest.raises(crypto.CryptoDecryptionError):
        crypto.decrypt("")
    with pytest.raises(crypto.CryptoDecryptionError):
        crypto.decrypt(b"")


def test_cross_secret_token_rejected(monkeypatch):
    token = crypto.encrypt("hello")
    monkeypatch.setenv("MASTER_KEY_SECRET", "entirely-different-master-secret-key-material-xx")
    crypto.reset_cache_for_tests()
    with pytest.raises(crypto.CryptoDecryptionError):
        crypto.decrypt(token)


def test_mask_long_and_short_values():
    assert crypto.mask("sk-1234567890ab") == "sk-...ab"
    assert crypto.mask("short") == "***"
    assert crypto.mask("12345678") == "***"
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
