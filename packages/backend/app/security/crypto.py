"""Slidoxa Fernet-based at-rest encryption for provider keys.

The Fernet derivation and token format are unchanged. Since the normalized
schema stores tokens as BYTEA, decrypt accepts both the historical TEXT
representation and the new bytes representation.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_HKDF_INFO = b"ogs-byok-v1"
_HKDF_SALT = b""


class CryptoConfigError(RuntimeError):
    """Raised when MASTER_KEY_SECRET is missing or unusable."""


class CryptoDecryptionError(RuntimeError):
    """Raised on any malformed, tampered, or foreign Fernet token."""


@dataclass(frozen=True)
class _DerivedKey:
    fernet: Fernet


def _load_master_secret() -> bytes:
    secret = os.getenv("MASTER_KEY_SECRET", "")
    if not secret:
        raise CryptoConfigError(
            "MASTER_KEY_SECRET is not set. Configure it in the Slidoxa environment."
        )
    if len(secret.encode("utf-8")) < 16:
        raise CryptoConfigError("MASTER_KEY_SECRET is too short; require at least 16 bytes.")
    return secret.encode("utf-8")


def _derive() -> _DerivedKey:
    material = _load_master_secret()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    )
    return _DerivedKey(fernet=Fernet(base64.urlsafe_b64encode(hkdf.derive(material))))


_cached: _DerivedKey | None = None


def _fernet() -> Fernet:
    global _cached
    if _cached is None:
        _cached = _derive()
    return _cached.fernet


def reset_cache_for_tests() -> None:
    """Reset the derived key cache after a test changes its environment."""
    global _cached
    _cached = None


def encrypt(plaintext: str) -> str:
    """Encrypt UTF-8 plaintext and return an ASCII Fernet token."""
    if not isinstance(plaintext, str):
        raise TypeError("encrypt() requires a str plaintext")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str | bytes | bytearray | memoryview) -> str:
    """Decrypt either the historical TEXT or current BYTEA token form."""
    if not token:
        raise CryptoDecryptionError("empty token")
    try:
        token_bytes = token.encode("ascii") if isinstance(token, str) else bytes(token)
        plaintext = _fernet().decrypt(token_bytes)
        return plaintext.decode("utf-8")
    except InvalidToken as exc:
        raise CryptoDecryptionError("invalid token") from exc
    except CryptoConfigError:
        raise
    except Exception as exc:  # pragma: no cover - defensive normalization
        raise CryptoDecryptionError("decrypt failed") from exc


def mask(secret: str) -> str:
    """Return the existing safe API display hint (first 3 + last 2 chars)."""
    if not isinstance(secret, str) or len(secret) <= 8:
        return "***"
    return f"{secret[:3]}...{secret[-2:]}"
