from datetime import timedelta

from sqlalchemy import select

from realtoruch.auth import AccountToken, AuthJob, AuthSession, LoginSession, RefreshToken, User, digest
from realtoruch.models import Favorite, now
from realtoruch.settings import get_settings

CREDENTIALS = {"email": "account@example.test", "password": "a-long-account-test-password"}


def signup(client, **extra):
    response = client.post("/v1/auth/register", json={**CREDENTIALS, **extra})
    assert response.status_code == 201, response.text
    result = response.json()
    return result, {"Authorization": "Bearer " + result["access_token"]}


def test_refresh_replay_revokes_access_and_rotated_refresh(auth_client, client):
    result, headers = signup(auth_client)
    assert client.get("/v1/me/favorites", headers=headers).status_code == 200
    rotated = auth_client.post("/v1/auth/refresh", json={"refresh_token": result["refresh_token"]})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != result["refresh_token"]
    with AuthSession() as session:
        assert session.get(RefreshToken, digest(result["refresh_token"])).used_at
        assert result["refresh_token"] not in str(session.scalars(select(RefreshToken.token_hash)).all())
    assert (
        auth_client.post("/v1/auth/refresh", json={"refresh_token": result["refresh_token"]}).status_code
        == 401
    )
    assert client.get("/v1/me/favorites", headers=headers).status_code == 401
    assert (
        auth_client.post(
            "/v1/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]}
        ).status_code
        == 401
    )


def test_web_refresh_cookie_and_csrf(auth_client):
    bad = auth_client.post(
        "/v1/auth/register", json={**CREDENTIALS, "client": "web"}, headers={"Origin": "https://evil.example"}
    )
    assert bad.status_code == 403
    response = auth_client.post(
        "/v1/auth/register",
        json={**CREDENTIALS, "client": "web"},
        headers={"Origin": "http://localhost:8081"},
    )
    assert response.status_code == 201
    assert "refresh_token" not in response.json()
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert "Path=/v1/auth" in response.headers["set-cookie"]
    assert auth_client.post("/v1/auth/refresh", json={}).status_code == 403
    assert (
        auth_client.post("/v1/auth/refresh", json={}, headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert (
        auth_client.post("/v1/auth/refresh", json={}, headers={"Origin": "http://localhost:8081"}).status_code
        == 200
    )


def test_session_revocation_is_owner_scoped_and_immediate(auth_client, client):
    first, h1 = signup(auth_client)
    second = auth_client.post("/v1/auth/login", json=CREDENTIALS).json()
    h2 = {"Authorization": "Bearer " + second["access_token"]}
    _, other = signup(auth_client, email="other@example.test")
    devices = auth_client.get("/v1/auth/sessions", headers=h1).json()["items"]
    assert len(devices) == 2
    sid = next(row["id"] for row in devices if not row["current"])
    assert auth_client.delete("/v1/auth/sessions/" + sid, headers=other).status_code == 404
    assert auth_client.delete("/v1/auth/sessions/" + sid, headers=h1).status_code == 200
    assert client.get("/v1/me/favorites", headers=h2).status_code == 401
    assert client.get("/v1/me/favorites", headers=h1).status_code == 200
    assert auth_client.post("/v1/auth/logout", headers=h1).status_code == 200
    assert auth_client.get("/v1/auth/me", headers=h1).status_code == 401
    assert (
        auth_client.post("/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code
        == 401
    )


def test_verification_reset_mail_retry_and_single_use(auth_client, monkeypatch):
    from realtoruch.auth_jobs import process_jobs

    monkeypatch.setattr(get_settings(), "email_delivery_mode", "file")
    _, headers = signup(auth_client)
    assert not auth_client.get("/v1/auth/me", headers=headers).json()["email_verified"]
    with AuthSession() as session:
        verify = session.scalar(select(AuthJob).where(AuthJob.kind == "verify")).secret
    assert auth_client.post("/v1/auth/verify-email", json={"token": verify}).status_code == 200
    assert auth_client.post("/v1/auth/verify-email", json={"token": verify}).status_code == 400
    assert auth_client.get("/v1/auth/me", headers=headers).json()["email_verified"]
    known = auth_client.post("/v1/auth/request-password-reset", json={"email": CREDENTIALS["email"]})
    unknown = auth_client.post("/v1/auth/request-password-reset", json={"email": "absent@example.test"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    auth_client.post("/v1/auth/request-password-reset", json={"email": CREDENTIALS["email"]})
    with AuthSession() as session:
        jobs = session.scalars(select(AuthJob).where(AuthJob.kind == "reset")).all()
        assert len(jobs) == 1  # resend cooldown
        reset, job_id = jobs[0].secret, jobs[0].id

    def fail(*args):
        raise ConnectionError("a private transport error")

    assert process_jobs(sender=fail) == 1
    with AuthSession.begin() as session:
        job = session.get(AuthJob, job_id)
        assert job.last_error == "ConnectionError"
        assert job.status == "retry"
        job.next_attempt_at = now() - timedelta(seconds=1)
    messages = []
    assert process_jobs(sender=lambda message, _: messages.append(message)) == 1
    assert "#reset_password=" + reset in messages[0].get_content()
    with AuthSession() as session:
        assert session.get(AuthJob, job_id).secret is None
    changed = {"token": reset, "password": "new-long-account-test-password"}
    assert auth_client.post("/v1/auth/reset-password", json=changed).status_code == 200
    assert auth_client.post("/v1/auth/reset-password", json=changed).status_code == 400
    assert auth_client.get("/v1/auth/me", headers=headers).status_code == 401
    assert auth_client.post("/v1/auth/login", json=CREDENTIALS).status_code == 401
    assert (
        auth_client.post("/v1/auth/login", json={**CREDENTIALS, "password": changed["password"]}).status_code
        == 200
    )


def test_expired_reset_link_cannot_change_password(auth_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "email_delivery_mode", "file")
    signup(auth_client)
    auth_client.post("/v1/auth/request-password-reset", json={"email": CREDENTIALS["email"]})
    with AuthSession.begin() as session:
        secret = session.scalar(select(AuthJob).where(AuthJob.kind == "reset")).secret
        session.get(AccountToken, digest(secret)).expires_at = now() - timedelta(seconds=1)
    assert (
        auth_client.post(
            "/v1/auth/reset-password", json={"token": secret, "password": CREDENTIALS["password"]}
        ).status_code
        == 400
    )


def test_account_deletion_is_reauthenticated_retried_and_cleans_rental_data(
    auth_client, client, session, record
):
    from realtoruch.auth_jobs import process_jobs
    from realtoruch.ingest import ingest

    result, headers = signup(auth_client)
    user_id = result["user"]["id"]
    listing_id = ingest(session, record)["listing_id"]
    client.put(f"/v1/me/favorites/{listing_id}", headers=headers)
    client.post("/v1/me/searches", headers=headers, json={"name": "Home", "filters": {"city": "Warszawa"}})
    client.put(f"/v1/me/seen/{listing_id}", headers=headers)
    assert (
        auth_client.request(
            "DELETE", "/v1/auth/account", json={"password": "wrong-long-password"}, headers=headers
        ).status_code
        == 401
    )
    assert client.delete(f"/internal/accounts/{user_id}").status_code == 403
    assert (
        auth_client.request(
            "DELETE", "/v1/auth/account", json={"password": CREDENTIALS["password"]}, headers=headers
        ).status_code
        == 202
    )
    assert client.get("/v1/me/favorites", headers=headers).status_code == 401
    assert auth_client.post("/v1/auth/login", json=CREDENTIALS).status_code == 401

    def offline(_):
        raise ConnectionError()

    process_jobs(eraser=offline)
    with AuthSession.begin() as identity:
        job = identity.scalar(select(AuthJob).where(AuthJob.kind == "delete"))
        assert job.status == "retry"
        assert identity.get(User, user_id).email != CREDENTIALS["email"]
        job.next_attempt_at = now() - timedelta(seconds=1)

    def erase(uid):
        response = client.delete(
            f"/internal/accounts/{uid}", headers={"X-Internal-Key": get_settings().internal_api_key}
        )
        assert response.status_code == 200

    process_jobs(eraser=erase)
    assert session.get(Favorite, (user_id, listing_id)) is None
    with AuthSession() as identity:
        assert identity.get(User, user_id) is None
        assert identity.scalar(select(LoginSession).where(LoginSession.user_id == user_id)) is None
    assert client.get(f"/v1/listings/{listing_id}").status_code == 200
    erase(user_id)  # idempotent cross-service cleanup
