"""Durable identity mail and account-erasure jobs. Run beside the auth service."""

import argparse
import time
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime

import httpx
from sqlalchemy import delete, or_, select, update

from .auth import AccountToken, AuthJob, AuthSession, LoginSession, User, digest, init_auth_db
from .delivery_claims import claim, finish, lock_owned
from .email_alerts import send_email
from .models import now
from .settings import get_settings


def erase_rental_data(user_id):
    settings = get_settings()
    response = httpx.delete(
        settings.api_base_url.rstrip("/") + f"/internal/accounts/{user_id}",
        headers={"X-Internal-Key": settings.internal_api_key},
        timeout=20,
    )
    response.raise_for_status()


def process_jobs(*, limit=20, sender=send_email, eraser=erase_rental_data):
    settings = get_settings()
    count = 0
    for _ in range(limit):
        with AuthSession.begin() as session:
            extra = (AuthJob.kind == "delete",) if settings.email_delivery_mode == "disabled" else ()
            job, token = claim(session, AuthJob, ["pending", "retry"], *extra)
            if not job:
                break
            user = session.get(User, job.user_id)
            if job.kind != "delete":
                link = session.get(AccountToken, digest(job.secret)) if job.secret else None
                if not user or user.deleted_at or not link or link.used_at or link.expires_at <= now() or job.attempts > 8:
                    finish(session, AuthJob, job.id, token, ["pending", "retry"],
                           {"status": "failed" if job.attempts > 8 else "cancelled", "secret": None})
                    continue
                message = EmailMessage()
                message["From"], message["To"] = settings.email_from, user.email
                message["Message-ID"] = f"<{job.id}@realtoruch.accounts>"
                message["Date"] = format_datetime(now())
                action = "reset_password" if job.kind == "reset" else "verify_account"
                message["Subject"] = ("Reset your Realtoruch password" if job.kind == "reset" else "Verify your Realtoruch email")
                message.set_content(
                    f"{message['Subject']}:\n\n{settings.public_web_url.rstrip('/')}/#{action}={job.secret}\n\n"
                    f"This link expires in {'30 minutes' if job.kind == 'reset' else 'one hour'}. "
                    "If you did not request this, ignore this email.\n"
                )
            elif user and not user.deleted_at:
                finish(session, AuthJob, job.id, token, ["pending", "retry"], {"status": "cancelled"})
                continue
            job_id, user_id, kind, attempts = job.id, job.user_id, job.kind, job.attempts
        error = None
        try:
            if kind == "delete":
                eraser(user_id)
            else:
                sender(message, job_id)
        except Exception as exc:
            error = type(exc).__name__[:100]
        with AuthSession.begin() as session:
            if not lock_owned(session, AuthJob, job_id, token, ["pending", "retry"]):
                continue
            job = session.get(AuthJob, job_id)
            user = session.get(User, user_id)
            link = session.get(AccountToken, digest(job.secret)) if kind != "delete" and job.secret else None
            invalid = kind != "delete" and (not user or user.deleted_at or not link or link.used_at or link.expires_at <= now())
            if invalid:
                values = {"status": "cancelled", "secret": None, "last_error": None}
            elif error:
                status = "retry" if kind == "delete" or attempts < 8 else "failed"
                values = {"status": status, "last_error": error,
                          "next_attempt_at": now() + timedelta(seconds=min(3600, 30 * 2 ** min(attempts, 7)))}
                if status == "failed":
                    values["secret"] = None
            else:
                values = {"status": "done", "secret": None, "last_error": None}
            owned = finish(session, AuthJob, job_id, token, ["pending", "retry"], values)
            if owned and not error and not invalid and kind == "delete":
                session.execute(delete(User).where(User.id == user_id, User.deleted_at.is_not(None)))
        count += 1
    # Retain spent refresh hashes until their session expires to detect reuse.
    with AuthSession.begin() as session:
        session.execute(delete(LoginSession).where(LoginSession.expires_at < now()))
        session.execute(delete(AccountToken).where(AccountToken.expires_at < now() - timedelta(days=1)))
        session.execute(
            delete(AuthJob).where(
                AuthJob.status.in_(["done", "cancelled", "failed"]),
                AuthJob.next_attempt_at < now() - timedelta(days=7),
            )
        )
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    if get_settings().environment != "production":
        init_auth_db()
    while True:
        print({"processed_auth_jobs": process_jobs()}, flush=True)
        if not args.loop:
            return
        time.sleep(5)


if __name__ == "__main__":
    main()
