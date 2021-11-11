import time
from collections import OrderedDict, deque

import jwt
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from .settings import get_settings


def require_claims(request: Request):
    value = request.headers.get("authorization", "")
    if not value.startswith("Bearer "):
        raise HTTPException(401, "Sign in to continue", headers={"WWW-Authenticate": "Bearer"})
    settings = get_settings()
    try:
        payload = jwt.decode(
            value[7:],
            settings.jwt_public_key.replace("\\n", "\n") or settings.jwt_secret,
            algorithms=["RS256"] if settings.jwt_public_key else ["HS256"],
            issuer=settings.jwt_issuer,
            audience="realtoruch",
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Session expired or invalid", headers={"WWW-Authenticate": "Bearer"})
    validator = getattr(request.app.state, "validate_claims", None)
    if validator:
        return validator(payload)
    # Fail closed for account operations if identity is unavailable. Public reads
    # remain available; the rental service never needs identity database access.
    try:
        response = httpx.get(
            settings.auth_service_url.rstrip("/") + "/v1/auth/me",
            headers={"Authorization": value},
            timeout=3,
        )
        if response.status_code == 401:
            raise HTTPException(401, "Session expired or revoked")
        response.raise_for_status()
        account = response.json()
        if account.get("id") != payload["sub"]:
            raise ValueError("Invalid identity response")
        return {**payload, "email": account["email"], "email_verified": account["email_verified"]}
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, "Sign-in service is temporarily unavailable") from None


def require_user(request: Request):
    return require_claims(request)["sub"]


def install_http(app, *, auth=False):
    from fastapi.middleware.cors import CORSMiddleware

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Account-Export-Token"],
        allow_credentials=auth,
    )
    windows = OrderedDict()

    @app.middleware("http")
    async def controls(request, call_next):
        if (
            settings.environment != "production"
            and request.url.path not in ("/healthz", "/readyz", "/metrics")
            and request.method != "OPTIONS"
        ):
            sensitive_auth = auth and request.url.path != "/v1/auth/me"
            key = (request.client.host if request.client else "unknown", sensitive_auth)
            current = time.monotonic()
            window = windows.setdefault(key, deque())
            windows.move_to_end(key)
            while window and window[0] <= current - 60:
                window.popleft()
            # Token validation is internal service traffic, still authenticated.
            limit = (
                settings.auth_request_limit_per_minute
                if sensitive_auth
                else settings.request_limit_per_minute
            )
            if len(window) >= limit:
                return JSONResponse(
                    {"detail": "Rate limit reached; try again shortly"}, 429, headers={"Retry-After": "60"}
                )
            window.append(current)
            if len(windows) > 10000:
                windows.popitem(last=False)
        try:
            length = int(request.headers.get("content-length", "0") or 0)
        except ValueError:
            return JSONResponse({"detail": "Invalid Content-Length"}, 400)
        if length > 1_000_000:
            return JSONResponse({"detail": "Request too large"}, 413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = ("private, no-store" if request.url.path in
                                             ("/v1/me/export", "/v1/auth/reauthenticate") else "no-store")
        return response
