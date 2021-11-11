"""Independent identity service with revocable sessions and one-use recovery links."""

import hashlib
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, delete, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .db import make_engine
from .models import now, uid
from .security import install_http, require_claims, require_user
from .settings import get_settings

settings = get_settings()
auth_engine = make_engine(settings.auth_database_url)
AuthSession = sessionmaker(auth_engine, expire_on_commit=False)
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("constant-time-missing-account-check")
COOKIE = "realtoruch_refresh"
COOKIE_PATH = "/v1/auth"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class AuthBase(DeclarativeBase):
    pass


class User(AuthBase):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LoginSession(AuthBase):
    __tablename__ = "login_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RefreshToken(AuthBase):
    __tablename__ = "refresh_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("login_sessions.id", ondelete="CASCADE"), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AccountToken(AuthBase):
    __tablename__ = "account_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuthJob(AuthBase):
    __tablename__ = "auth_jobs"
    __table_args__ = (Index("ix_auth_jobs_due", "status", "next_attempt_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(100), nullable=True)


class EmailBody(BaseModel):
    email: str = Field(min_length=5, max_length=254)

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


class PasswordBody(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class Credentials(EmailBody, PasswordBody):
    client: Literal["web", "native"] = "native"


class TokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=128)


class ResetBody(TokenBody, PasswordBody):
    pass


class RefreshBody(BaseModel):
    refresh_token: str | None = Field(None, min_length=20, max_length=128)


def init_auth_db():
    if auth_engine.dialect.name != "sqlite":
        from .migrations import apply_postgres
        with auth_engine.begin() as connection:
            apply_postgres(connection, "auth")
        return
    AuthBase.metadata.create_all(auth_engine)
    columns = {c["name"] for c in inspect(auth_engine).get_columns("users")}
    with auth_engine.begin() as connection:
        for column in ("verified_at", "deleted_at"):
            if column not in columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column} TIMESTAMP"))
    from .migrations import upgrade_local
    upgrade_local(auth_engine, "auth")


@asynccontextmanager
async def lifespan(app):
    if settings.environment == "production" and not settings.jwt_private_key:
        raise RuntimeError("Auth service requires JWT_PRIVATE_KEY in production")
    if settings.environment != "production":
        init_auth_db()
    yield


app = FastAPI(title="Realtoruch · Authentication", version="0.2.0", lifespan=lifespan)
install_http(app, auth=True)


def public_user(user):
    return {"id": user.id, "email": user.email, "email_verified": bool(user.verified_at)}


def validate_claims(payload):
    with AuthSession() as session:
        login = session.get(LoginSession, payload.get("sid", ""))
        user = session.get(User, payload["sub"])
        if (
            not user
            or user.deleted_at
            or not login
            or login.user_id != user.id
            or login.revoked_at
            or login.expires_at <= now()
        ):
            raise HTTPException(401, "Session expired or revoked", headers={"WWW-Authenticate": "Bearer"})
        return {**payload, "email": user.email, "email_verified": bool(user.verified_at)}


# The API validates signed tokens through this service; only auth reads the identity database.
app.state.validate_claims = validate_claims


def browser_origin(request):
    if request.headers.get("origin", "") not in settings.cors_origins.split(","):
        raise HTTPException(403, "This browser origin is not allowed")


def token(session, user, login, request, response, *, browser=False):
    issued = now()
    value = jwt.encode(
        {
            "sub": user.id,
            "sid": login.id,
            "email": user.email,
            "iss": settings.jwt_issuer,
            "aud": "realtoruch",
            "iat": issued,
            "exp": issued + timedelta(minutes=15),
        },
        settings.jwt_private_key.replace("\\n", "\n") or settings.jwt_secret,
        algorithm="RS256" if settings.jwt_private_key else "HS256",
    )
    refresh = secrets.token_urlsafe(48)
    session.add(RefreshToken(token_hash=digest(refresh), session_id=login.id))
    login.last_used_at = issued
    result = {"access_token": value, "token_type": "bearer", "expires_in": 900, "user": public_user(user)}
    if browser:
        browser_origin(request)
        response.set_cookie(
            COOKIE,
            refresh,
            httponly=True,
            secure=settings.environment == "production",
            samesite="strict",
            path=COOKIE_PATH,
            max_age=max(0, int((login.expires_at - issued).total_seconds())),
        )
    else:
        result["refresh_token"] = refresh
    session.commit()
    return result


def begin_session(session, user, body, request, response):
    login = LoginSession(
        user_id=user.id,
        label=device_label(request.headers.get("user-agent", "App")),
        expires_at=now() + timedelta(days=30),
    )
    session.add(login)
    session.flush()
    return token(session, user, login, request, response, browser=body.client == "web")


def device_label(agent):
    if agent in ("Mobile app", "API client"):
        return agent
    if " on " in agent and len(agent) < 50:
        return agent
    platform = (
        "Android"
        if "Android" in agent
        else "iOS"
        if "iPhone" in agent or "iPad" in agent
        else "macOS"
        if "Macintosh" in agent
        else "Windows"
        if "Windows" in agent
        else "Linux"
    )
    browser = (
        "Edge"
        if "Edg/" in agent
        else "Chrome"
        if "Chrome/" in agent
        else "Firefox"
        if "Firefox/" in agent
        else "Safari"
        if "Safari/" in agent
        else None
    )
    return (
        f"{browser} on {platform}"
        if browser
        else "Mobile app"
        if "Darwin" in agent or "okhttp" in agent
        else "API client"
    )


def check_password(user, password):
    try:
        hasher.verify(user.password_hash if user else DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        raise HTTPException(401, "Email or password is incorrect") from None
    if not user or user.deleted_at:
        raise HTTPException(401, "Email or password is incorrect")


def queue_link(session, user, kind):
    if settings.email_delivery_mode == "disabled":
        return False
    recent = session.scalar(
        select(AccountToken).where(
            AccountToken.user_id == user.id,
            AccountToken.kind == kind,
            AccountToken.created_at > now() - timedelta(minutes=1),
        )
    )
    if recent:
        return False
    session.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user.id,
            AccountToken.kind == kind,
            AccountToken.used_at.is_(None),
        )
        .values(used_at=now())
    )
    secret = secrets.token_urlsafe(32)
    session.add(
        AccountToken(
            token_hash=digest(secret),
            user_id=user.id,
            kind=kind,
            expires_at=now() + timedelta(minutes=30 if kind == "reset" else 60),
        )
    )
    session.add(AuthJob(user_id=user.id, kind=kind, secret=secret))
    return True


@app.get("/healthz")
def health():
    return {"status": "ok", "service": "auth"}


@app.post("/v1/auth/register", status_code=201)
def register(body: Credentials, request: Request, response: Response):
    if body.client == "web":
        browser_origin(request)
    with AuthSession() as session:
        user = User(email=body.email, password_hash=hasher.hash(body.password))
        session.add(user)
        try:
            session.flush()
        except IntegrityError:
            raise HTTPException(409, "Account could not be created with this email") from None
        queue_link(session, user, "verify")
        return begin_session(session, user, body, request, response)


@app.post("/v1/auth/login")
def login(body: Credentials, request: Request, response: Response):
    if body.client == "web":
        browser_origin(request)
    with AuthSession() as session:
        user = session.scalar(select(User).where(User.email == body.email))
        check_password(user, body.password)
        if hasher.check_needs_rehash(user.password_hash):
            user.password_hash = hasher.hash(body.password)
        return begin_session(session, user, body, request, response)


@app.post("/v1/auth/refresh")
def refresh(body: RefreshBody, request: Request, response: Response):
    browser = body.refresh_token is None
    if browser:
        browser_origin(request)
    value = request.cookies.get(COOKIE, "") if browser else body.refresh_token
    with AuthSession() as session:
        stored = session.get(RefreshToken, digest(value))
        login = session.get(LoginSession, stored.session_id) if stored else None
        user = session.get(User, login.user_id) if login else None
        if not user or user.deleted_at or not login or login.revoked_at or login.expires_at <= now():
            raise HTTPException(401, "Sign in again to continue")
        consumed = session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == stored.token_hash,
                RefreshToken.used_at.is_(None),
            )
            .values(used_at=now())
        ).rowcount
        if not consumed:
            login.revoked_at = now()
            session.commit()  # Replayed refresh invalidates its entire session family.
            raise HTTPException(401, "Session revoked; sign in again")
        return token(session, user, login, request, response, browser=browser)


@app.get("/v1/auth/me")
def me(claims=Depends(require_claims)):
    return {"id": claims["sub"], "email": claims["email"], "email_verified": claims["email_verified"]}


@app.post("/v1/auth/logout")
def logout(response: Response, claims=Depends(require_claims)):
    with AuthSession.begin() as session:
        session.get(LoginSession, claims["sid"]).revoked_at = now()
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    return {"signed_out": True}


@app.get("/v1/auth/sessions")
def sessions(claims=Depends(require_claims)):
    with AuthSession() as session:
        rows = session.scalars(
            select(LoginSession)
            .where(
                LoginSession.user_id == claims["sub"],
                LoginSession.revoked_at.is_(None),
                LoginSession.expires_at > now(),
            )
            .order_by(LoginSession.last_used_at.desc())
            .limit(100)
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "label": device_label(row.label),
                    "current": row.id == claims["sid"],
                    "created_at": row.created_at.isoformat() + "Z",
                    "last_used_at": row.last_used_at.isoformat() + "Z",
                }
                for row in rows
            ]
        }


@app.delete("/v1/auth/sessions/{session_id}")
def revoke(session_id: str, user_id=Depends(require_user)):
    with AuthSession.begin() as session:
        row = session.get(LoginSession, session_id)
        if not row or row.user_id != user_id:
            raise HTTPException(404, "Session not found")
        row.revoked_at = now()
    return {"revoked": True}


@app.post("/v1/auth/request-verification", status_code=202)
def request_verification(user_id=Depends(require_user)):
    if settings.email_delivery_mode == "disabled":
        raise HTTPException(503, "Email delivery is not configured")
    with AuthSession.begin() as session:
        user = session.get(User, user_id)
        if not user.verified_at:
            queue_link(session, user, "verify")
    return {"message": "If verification is needed, an email will arrive shortly."}


@app.post("/v1/auth/request-password-reset", status_code=202)
def request_reset(body: EmailBody):
    if settings.email_delivery_mode == "disabled":
        raise HTTPException(503, "Email delivery is not configured")
    with AuthSession.begin() as session:
        user = session.scalar(select(User).where(User.email == body.email, User.deleted_at.is_(None)))
        if user:
            queue_link(session, user, "reset")
    return {"message": "If this account exists, a password reset email will arrive shortly."}


def consume_link(session, value, kind):
    row = session.get(AccountToken, digest(value))
    user = session.get(User, row.user_id) if row else None
    if not row or row.kind != kind or row.expires_at <= now() or not user or user.deleted_at:
        raise HTTPException(400, "This link is invalid or has expired")
    consumed = session.execute(
        update(AccountToken)
        .where(
            AccountToken.token_hash == row.token_hash,
            AccountToken.used_at.is_(None),
        )
        .values(used_at=now())
    ).rowcount
    if not consumed:
        raise HTTPException(400, "This link has already been used")
    return user


@app.post("/v1/auth/verify-email")
def verify(body: TokenBody):
    with AuthSession.begin() as session:
        user = consume_link(session, body.token, "verify")
        user.verified_at = now()
    return {"message": "Email verified. You can return to your account."}


@app.post("/v1/auth/reset-password")
def reset_password(body: ResetBody, response: Response):
    with AuthSession.begin() as session:
        user = consume_link(session, body.token, "reset")
        user.password_hash = hasher.hash(body.password)
        session.execute(update(LoginSession).where(LoginSession.user_id == user.id).values(revoked_at=now()))
        session.execute(
            update(AccountToken)
            .where(
                AccountToken.user_id == user.id,
                AccountToken.kind == "reset",
            )
            .values(used_at=now())
        )
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    return {"message": "Password changed. Sign in again on your devices."}


@app.delete("/v1/auth/account", status_code=202)
def delete_account(body: PasswordBody, response: Response, user_id=Depends(require_user)):
    with AuthSession.begin() as session:
        user = session.get(User, user_id)
        check_password(user, body.password)
        user.deleted_at, user.email, user.password_hash = (
            now(),
            f"deleted-{user.id}@example.invalid",
            DUMMY_HASH,
        )
        session.execute(update(LoginSession).where(LoginSession.user_id == user.id).values(revoked_at=now()))
        session.execute(delete(AccountToken).where(AccountToken.user_id == user.id))
        session.execute(
            update(AuthJob).where(AuthJob.user_id == user.id).values(secret=None, status="cancelled")
        )
        session.add(AuthJob(user_id=user.id, kind="delete"))
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    return {"message": "Account disabled. Deletion of saved data is queued and will retry until complete."}
