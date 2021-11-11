import re
from contextlib import asynccontextmanager
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .db import make_engine
from .models import now, uid
from .security import install_http, require_user
from .settings import get_settings

settings = get_settings()
auth_engine = make_engine(settings.auth_database_url)
AuthSession = sessionmaker(auth_engine, expire_on_commit=False)
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("constant-time-missing-account-check")


class AuthBase(DeclarativeBase):
    pass


class User(AuthBase):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        from email.headerregistry import Address

        try:
            Address(addr_spec=value)
        except ValueError:
            raise ValueError("Enter a single valid email address") from None
        return value


@asynccontextmanager
async def lifespan(app):
    if settings.environment == "production" and not settings.jwt_private_key:
        raise RuntimeError("Auth service requires JWT_PRIVATE_KEY in production")
    if settings.environment != "production":
        AuthBase.metadata.create_all(auth_engine)
    yield


app = FastAPI(title="Realtoruch · Authentication", version="0.1.0", lifespan=lifespan)
install_http(app, auth=True)


def token(user):
    issued = now()
    value = jwt.encode(
        {
            "sub": user.id,
            "email": user.email,
            "iss": settings.jwt_issuer,
            "aud": "realtoruch",
            "iat": issued,
            "exp": issued + timedelta(hours=1),
        },
        settings.jwt_private_key.replace("\\n", "\n") or settings.jwt_secret,
        algorithm="RS256" if settings.jwt_private_key else "HS256",
    )
    return {
        "access_token": value,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {"id": user.id, "email": user.email},
    }


@app.get("/healthz")
def health():
    return {"status": "ok", "service": "auth"}


@app.post("/v1/auth/register", status_code=201)
def register(body: Credentials):
    with AuthSession() as session:
        user = User(email=body.email, password_hash=hasher.hash(body.password))
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            raise HTTPException(409, "Account could not be created with this email")
        return token(user)


@app.post("/v1/auth/login")
def login(body: Credentials):
    with AuthSession() as session:
        user = session.scalar(select(User).where(User.email == body.email))
        try:
            hasher.verify(user.password_hash if user else DUMMY_HASH, body.password)
        except (VerificationError, InvalidHashError):
            raise HTTPException(401, "Email or password is incorrect")
        if not user:
            raise HTTPException(401, "Email or password is incorrect")
        return token(user)


@app.get("/v1/auth/me")
def me(user_id=Depends(require_user)):
    with AuthSession() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(401, "Account no longer exists")
        return {"id": user.id, "email": user.email}
