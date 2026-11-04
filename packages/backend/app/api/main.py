"""Slidoxa native FastAPI application.

Entrypoint: ``app.api.main:app``. Mounts the health, auth and
provider-key routers. Does not import from packages/backend/app/legacy/
so the inherited Presenton stack is untouched.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api import db as db_module
from app.api.models import ProviderKey, User
from app.security import auth as auth_mod
from app.security import crypto


app = FastAPI(title="Slidoxa API", version="0.1.0")


# ----------------------------- schemas -------------------------------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ProviderKeyIn(BaseModel):
    provider: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    api_key: str = Field(min_length=1, max_length=4096)


class ProviderKeyOut(BaseModel):
    provider: str
    masked_key: str


class MeOut(BaseModel):
    id: str
    email: str


# ----------------------------- helpers -------------------------------


def _get_user(session: Session, principal: auth_mod.Principal) -> User:
    user = session.get(User, principal.sub)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


# ----------------------------- routes --------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=MeOut)
def register(
    payload: RegisterIn,
    response: Response,
    session: Session = Depends(db_module.get_session),
) -> MeOut:
    user = User(
        email=payload.email.lower(),
        password_hash=auth_mod.hash_password(payload.password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        )
    session.refresh(user)
    auth_mod.issue_session_cookies(response, subject=str(user.id))
    return MeOut(id=str(user.id), email=user.email)


@app.post("/auth/login", response_model=MeOut)
def login(
    payload: LoginIn,
    response: Response,
    session: Session = Depends(db_module.get_session),
) -> MeOut:
    user = session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not auth_mod.verify_password(user.password_hash, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if auth_mod.needs_rehash(user.password_hash):
        user.password_hash = auth_mod.hash_password(payload.password)
        session.commit()
    auth_mod.issue_session_cookies(response, subject=str(user.id))
    return MeOut(id=str(user.id), email=user.email)


@app.get("/auth/me", response_model=MeOut)
def me(
    principal: auth_mod.Principal = Depends(auth_mod.current_user),
    session: Session = Depends(db_module.get_session),
) -> MeOut:
    user = _get_user(session, principal)
    return MeOut(id=str(user.id), email=user.email)


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    _principal: auth_mod.Principal = Depends(auth_mod.current_user),
    _csrf: None = Depends(auth_mod.csrf_guard),
) -> Response:
    auth_mod.clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.get("/provider-keys", response_model=list[ProviderKeyOut])
def list_provider_keys(
    principal: auth_mod.Principal = Depends(auth_mod.current_user),
    session: Session = Depends(db_module.get_session),
) -> list[ProviderKeyOut]:
    rows = session.scalars(
        select(ProviderKey).where(ProviderKey.owner_id == principal.sub)
    ).all()
    out: list[ProviderKeyOut] = []
    for row in rows:
        try:
            plain = crypto.decrypt(row.encrypted_key)
            masked = crypto.mask(plain)
        except crypto.CryptoDecryptionError:
            masked = "***"
        out.append(ProviderKeyOut(provider=row.provider, masked_key=masked))
    return out


@app.put("/provider-keys", response_model=ProviderKeyOut)
def upsert_provider_key(
    payload: ProviderKeyIn,
    principal: auth_mod.Principal = Depends(auth_mod.current_user),
    _csrf: None = Depends(auth_mod.csrf_guard),
    session: Session = Depends(db_module.get_session),
) -> ProviderKeyOut:
    encrypted = crypto.encrypt(payload.api_key)
    existing = session.scalar(
        select(ProviderKey).where(
            ProviderKey.owner_id == principal.sub,
            ProviderKey.provider == payload.provider,
        )
    )
    if existing is None:
        session.add(
            ProviderKey(
                owner_id=principal.sub,
                provider=payload.provider,
                encrypted_key=encrypted,
            )
        )
    else:
        existing.encrypted_key = encrypted
    session.commit()
    return ProviderKeyOut(provider=payload.provider, masked_key=crypto.mask(payload.api_key))


@app.delete("/provider-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_key(
    provider: str,
    principal: auth_mod.Principal = Depends(auth_mod.current_user),
    _csrf: None = Depends(auth_mod.csrf_guard),
    session: Session = Depends(db_module.get_session),
) -> Response:
    row = session.scalar(
        select(ProviderKey).where(
            ProviderKey.owner_id == principal.sub,
            ProviderKey.provider == provider,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    session.delete(row)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
