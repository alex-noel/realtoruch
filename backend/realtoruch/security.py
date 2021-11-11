import time
from collections import OrderedDict, deque

import jwt
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
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Session expired or invalid", headers={"WWW-Authenticate": "Bearer"})


def require_user(request: Request):
    return require_claims(request)["sub"]


def install_http(app, *, auth=False):
    from fastapi.middleware.cors import CORSMiddleware

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )
    windows = OrderedDict()

    @app.middleware("http")
    async def controls(request, call_next):
        if (
            settings.environment != "production"
            and request.url.path not in ("/healthz", "/readyz", "/metrics")
            and request.method != "OPTIONS"
        ):
            key = request.client.host if request.client else "unknown"
            current = time.monotonic()
            window = windows.setdefault(key, deque())
            windows.move_to_end(key)
            while window and window[0] <= current - 60:
                window.popleft()
            limit = 20 if auth else settings.request_limit_per_minute
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
        response.headers["Cache-Control"] = "no-store"
        return response
