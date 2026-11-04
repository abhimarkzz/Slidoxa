"""Slidoxa authentication primitives.

Design goals:
- Argon2id password hashing (argon2-cffi defaults; PasswordHasher).
- Short-lived JWT access tokens (15 min) signed with ``JWT_SECRET``.
- HttpOnly access cookie + a separate CSRF cookie + ``X-CSRF`` header.
- SameSite=Strict, Secure by default; Secure can be disabled only for
  local development via ``COOKIE_SECURE=false``.
- 401 on auth failure, 403 on CSRF failure.
- These primitives are standalone and do NOT touch the inherited
  Presenton auth stack in packages/backend/app/legacy/. They are
  intended to be mounted on Slidoxa-owned routers (packages/backend/
  app/api/) once that surface exists. The legacy Electron desktop
  token in api/v1/auth/desktop.py is unaffected.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status

ACCESS_COOKIE_NAME = "ogs_access"
CSRF_COOKIE_NAME = "ogs_csrf"
CSRF_HEADER_NAME = "X-CSRF"

_JWT_ALG = "HS256"
_ACCESS_TTL = timedelta(minutes=15)

_password_hasher = PasswordHasher()


class AuthConfigError(RuntimeError):
    """JWT_SECRET missing or weak."""


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise AuthConfigError(
            "JWT_SECRET is not set. Generate with "
            "`openssl rand -base64 48` and configure in the Slidoxa env."
        )
    if len(secret.encode("utf-8")) < 32:
        raise AuthConfigError("JWT_SECRET is too short (require >=32 bytes).")
    return secret


def _cookie_secure() -> bool:
    val = os.getenv("COOKIE_SECURE", "true").strip().lower()
    return val not in {"0", "false", "no", "off"}


# ---------- passwords -------------------------------------------------


def hash_password(password: str) -> str:
    if not password or not isinstance(password, str):
        raise ValueError("password must be a non-empty string")
    return _password_hasher.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        _password_hasher.verify(hashed, password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _password_hasher.check_needs_rehash(hashed)


# ---------- tokens ----------------------------------------------------


@dataclass(frozen=True)
class Principal:
    sub: str  # user id
    exp: int  # expiry epoch seconds


def issue_access_token(subject: str, *, now: datetime | None = None) -> str:
    if not subject:
        raise ValueError("subject is required")
    moment = now or datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(moment.timestamp()),
        "exp": int((moment + _ACCESS_TTL).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALG)


def verify_access_token(token: str) -> Principal:
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[_JWT_ALG],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token expired"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from exc
    return Principal(sub=str(payload["sub"]), exp=int(payload["exp"]))


# ---------- cookies ---------------------------------------------------


def _set_cookie(response: Response, name: str, value: str, *, http_only: bool) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=int(_ACCESS_TTL.total_seconds()),
        httponly=http_only,
        secure=_cookie_secure(),
        samesite="strict",
        path="/",
    )


def issue_session_cookies(response: Response, subject: str) -> str:
    """Set access + CSRF cookies. Returns the CSRF token value so the
    frontend can mirror it into the X-CSRF header on state-changing
    requests."""
    token = issue_access_token(subject)
    csrf = secrets.token_urlsafe(32)
    _set_cookie(response, ACCESS_COOKIE_NAME, token, http_only=True)
    _set_cookie(response, CSRF_COOKIE_NAME, csrf, http_only=False)
    return csrf


def clear_session_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME):
        response.delete_cookie(key=name, path="/", samesite="strict")


# ---------- dependencies ---------------------------------------------


def current_user(
    access: Annotated[str | None, Cookie(alias=ACCESS_COOKIE_NAME)] = None,
) -> Principal:
    if not access:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated"
        )
    return verify_access_token(access)


def csrf_guard(
    request: Request,
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
) -> None:
    """Enforce double-submit CSRF for cookie-authenticated state-changing requests."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not csrf_cookie or not csrf_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF missing")
    # constant-time compare
    if not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF invalid")


# ---------- dependency bundles ---------------------------------------


def protected() -> list[Callable]:
    """Dependency list for state-changing Slidoxa routes."""
    return [Depends(current_user), Depends(csrf_guard)]
