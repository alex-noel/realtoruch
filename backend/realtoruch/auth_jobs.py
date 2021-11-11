"""Durable identity mail and account-erasure jobs. Run beside the auth service."""

import argparse
import time
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime

import httpx
from sqlalchemy import delete, or_, select, update

from .auth import AccountToken, AuthJob, AuthSession, LoginSession, User, digest, init_auth_db
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
            job = session.scalar(
                select(AuthJob)
                .where(
                    AuthJob.status.in_(["pending", "retry"]),
                    AuthJob.next_attempt_at <= now(),
                    or_(AuthJob.lease_until.is_(None), AuthJob.lease_until < now()),
                )
                .order_by(AuthJob.next_attempt_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not job:
                break
            user = session.get(User, job.user_id)
            if job.kind != "delete":
                link = session.get(AccountToken, digest(job.secret)) if job.secret else None
                if not user or user.deleted_at or not link or link.used_at or link.expires_at <= now():
                    job.status, job.secret = "cancelled", None
                    continue
                if settings.email_delivery_mode == "disabled":
                    break
                message = EmailMessage()
                message["From"], message["To"] = settings.email_from, user.email
                message["Message-ID"] = f"<{job.id}@realtoruch.accounts>"
                message["Date"] = format_datetime(now())
                action = "reset_password" if job.kind == "reset" else "verify_account"
                message["Subject"] = (
                    "Reset your Realtoruch password"
                    if job.kind == "reset"
                    else "Verify your Realtoruch email"
                )
                message.set_content(
                    f"{message['Subject']}:\n\n{settings.public_web_url.rstrip('/')}/#{action}={job.secret}\n\n"
                    f"This link expires in {'30 minutes' if job.kind == 'reset' else 'one hour'}. "
                    "If you did not request this, ignore this email.\n"
                )
            elif user and not user.deleted_at:
                job.status = "cancelled"
                continue
            # CAS also prevents two local SQLite workers claiming the same job.
            claim = session.execute(
                update(AuthJob)
                .where(
                    AuthJob.id == job.id,
                    or_(AuthJob.lease_until.is_(None), AuthJob.lease_until < now()),
                )
                .values(lease_until=now() + timedelta(seconds=60), attempts=AuthJob.attempts + 1)
            )
            if not claim.rowcount:
                continue
            job_id, user_id, kind = job.id, job.user_id, job.kind
        error = None
        try:
            if kind == "delete":
                eraser(user_id)
            else:
                sender(message, job_id)
        except Exception as exc:
            error = type(exc).__name__
        with AuthSession.begin() as session:
            job = session.get(AuthJob, job_id)
            if not job:
                continue
            job.lease_until, job.last_error = None, error
            # A simultaneous account deletion can cancel an in-flight email.
            if job.status == "cancelled":
                continue
            if error:
                job.status = "retry" if kind == "delete" or job.attempts < 8 else "failed"
                job.next_attempt_at = now() + timedelta(seconds=min(3600, 30 * 2 ** min(job.attempts, 7)))
                if job.status == "failed":
                    job.secret = None
            else:
                job.status, job.secret = "done", None
                if kind == "delete":
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
