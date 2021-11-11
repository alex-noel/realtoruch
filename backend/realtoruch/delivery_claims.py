"""Atomic, per-attempt leases shared by delivery workers."""

import logging
import secrets
from datetime import timedelta

from sqlalchemy import or_, select, update

from .models import now

log = logging.getLogger(__name__)


def claim(session, model, statuses, *extra):
    timestamp = now()
    eligible = (model.status.in_(statuses), model.next_attempt_at <= timestamp,
                or_(model.lease_until.is_(None), model.lease_until < timestamp), *extra)
    candidate = (select(model.id).where(*eligible).order_by(model.next_attempt_at, model.id)
                 .limit(1).with_for_update(skip_locked=True).scalar_subquery())
    token = secrets.token_hex(32)
    row = session.execute(
        update(model).where(model.id == candidate, *eligible)
        .values(claim_token=token, lease_until=timestamp + timedelta(seconds=60),
                attempts=model.attempts + 1)
        .returning(model.id), execution_options={"synchronize_session": False}
    ).first()
    return (session.get(model, row[0]), token) if row else (None, None)


def lock_owned(session, model, job_id, token, statuses):
    """Serialize final validation/side effects with takeover on both databases."""
    row = session.execute(
        update(model).where(model.id == job_id, model.claim_token == token,
                            model.status.in_(statuses))
        .values(claim_token=model.claim_token).returning(model.id),
        execution_options={"synchronize_session": False},
    ).first()
    return bool(row)


def finish(session, model, job_id, token, statuses, values):
    result = session.execute(
        update(model).where(model.id == job_id, model.claim_token == token,
                            model.status.in_(statuses))
        .values(claim_token=None, lease_until=None, **values).returning(model.attempts),
        execution_options={"synchronize_session": False},
    )
    row = result.first()
    log.info("delivery transition type=%s status=%s owned=%s attempt=%s", model.__tablename__,
             values.get("status", "unchanged"), bool(row), row[0] if row else None)
    return bool(row)


def cancel_notifications(session, *, notification_id=None, user_id=None, listing_id=None,
                         kind=None, subscription_id=None):
    """Cancel unsent work in the same transaction as its invalidating change.

    Accepted Expo tickets are left for receipt reconciliation.
    """
    from .models import EmailDelivery, Notification, PushDelivery

    filters = []
    for column, value in ((Notification.id, notification_id), (Notification.user_id, user_id),
                          (Notification.listing_id, listing_id), (Notification.kind, kind)):
        if value is not None:
            filters.append(column == value)
    if not filters and subscription_id is None:
        raise ValueError("A cancellation scope is required")
    ids = select(Notification.id).where(*filters)
    with session.no_autoflush:
        if subscription_id is None:
            session.execute(update(EmailDelivery).where(
                EmailDelivery.notification_id.in_(ids), EmailDelivery.status.in_(["pending", "retry"])
            ).values(status="cancelled", claim_token=None, lease_until=None, confirmation_token=None))
        push = update(PushDelivery).where(PushDelivery.status.in_(["pending", "retry"]),
                                          PushDelivery.receipt_id.is_(None))
        if filters:
            push = push.where(PushDelivery.notification_id.in_(ids))
        if subscription_id is not None:
            push = push.where(PushDelivery.subscription_id == subscription_id)
        session.execute(push.values(status="cancelled", claim_token=None, lease_until=None))
