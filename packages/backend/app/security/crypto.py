"""Slidoxa Fernet-based at-rest encryption for user-supplied keys.

HKDF-SHA256 derives a 32-byte Fernet key from ``MASTER_KEY_SECRET`` under
the fixed info string ``ogs-byok-v1``. Plaintext is never logged, and
invalid tokens raise a typed error instead of leaking details.

Masking rule (per spec):
    * secrets longer than 8 chars   -> ``abc...yz``
    * secrets 8 chars or shorter    -> ``***``
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_HKDF_INFO = b"ogs-byok-v1"
_HKDF_SALT = b""  # Deterministic: salt is empty by design; MASTER_KEY_SECRET is the input entropy.


class CryptoConfigError(RuntimeError):
    """Raised when MASTER_KEY_SECRET is missing or unusable."""


class CryptoDecryptionError(RuntimeError):
    """Raised on any Fernet decrypt failure. Carries no plaintext detail."""


@dataclass(frozen=True)
class _DerivedKey:
    fernet: Fernet


def _load_master_secret() -> bytes:
    secret = os.getenv("MASTER_KEY_SECRET", "")
    if not secret:
        raise CryptoConfigError(
            "MASTER_KEY_SECRET is not set. Generate one with "
            "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"` "
            "and configure it in the Slidoxa environment."
        )
    if len(secret.encode("utf-8")) < 16:
        raise CryptoConfigError(
            "MASTER_KEY_SECRET is too short. Supply at least 16 bytes of entropy."
        )
    return secret.encode("utf-8")


def _derive() -> _DerivedKey:
    material = _load_master_secret()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    )
    key = hkdf.derive(material)
    fernet_key = base64.urlsafe_b64encode(key)
    return _DerivedKey(fernet=Fernet(fernet_key))


# Cache the derived key at import time only if the env is already set;
# otherwise defer until first call so tests can set the env per-test.
_cached: _DerivedKey | None = None


def _fernet() -> Fernet:
    global _cached
    if _cached is None:
        _cached = _derive()
    return _cached.fernet


def reset_cache_for_tests() -> None:
    """Allow tests to re-derive after mutating MASTER_KEY_SECRET."""
    global _cached
    _cached = None


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 secret and return a urlsafe base64 Fernet token."""
    if not isinstance(plaintext, str):
        raise TypeError("encrypt() requires a str plaintext")
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token produced by ``encrypt``.

    Raises CryptoDecryptionError for any malformed, tampered, or
    foreign token. Never surfaces the underlying cryptography message.
    """
    if not isinstance(token, str) or not token:
        raise CryptoDecryptionError("empty or non-string token")
    try:
        plaintext = _fernet().decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        raise CryptoDecryptionError("invalid token") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise CryptoDecryptionError("decrypt failed") from exc
    return plaintext.decode("utf-8")


def mask(secret: str) -> str:
    """Return a safe display representation of a secret.

    >>> mask("sk-1234567890ab")
    'sk-...ab'
    >>> mask("short")
    '***'
    """
    if not isinstance(secret, str) or len(secret) <= 8:
        return "***"
    return f"{secret[:3]}...{secret[-2:]}"
