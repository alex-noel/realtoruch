"""Exercise actual grants on fresh, disposable PostgreSQL databases."""
import json
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session, sessionmaker

from realtoruch.delivery_claims import cancel_notifications

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_role_grants(monkeypatch, record):
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("requires disposable PostgreSQL")
    # The service runner owns this server. Never run against a developer catalog.
    if not os.environ.get("VERIFY_RUN_ID"):
        pytest.fail("grant test requires the isolated verification runner")
    params = conninfo_to_dict(url.replace("postgresql+psycopg://", "postgresql://"))
    if params.get("host") not in {"127.0.0.1", "::1"} or not params.get("dbname", "").startswith("r_"):
        pytest.fail("grant test requires the runner-owned loopback database")
    suffix = uuid4().hex[:12]
    databases = {name: f"t28_{name}_{suffix}" for name in ("rentals", "auth")}
    roles = {name: f"t28_{name}_{suffix}" for name in ("api", "auth", "indexer", "alerts", "dataflow")}
    registry = json.loads((ROOT / "infra/sql/migrations.json").read_text())
    with psycopg.connect(make_conninfo(**params), autocommit=True) as admin:
        try:
            for role in roles.values():
                admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
            for db in databases.values():
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db)))
            for logical, database in databases.items():
                dbparams = {**params, "dbname": database}
                with psycopg.connect(make_conninfo(**dbparams), autocommit=True) as conn:
                    for migration in registry[logical]:
                        conn.execute((ROOT / "infra/sql" / migration["file"]).read_text())
                    if logical == "rentals":
                        # Simulate the previous table-wide grants on upgrade.
                        conn.execute(sql.SQL("GRANT SELECT, UPDATE ON account_closures, collection_fetch_state TO {}").format(sql.Identifier(roles["api"])))
                        conn.execute(sql.SQL("GRANT ALL ON email_deliveries, push_deliveries, listings TO {}").format(sql.Identifier(roles["dataflow"])))
                    grants = (ROOT / "infra/sql/grants.sql").read_text().split("\\connect " + logical + "\n", 1)[1].split("\\connect ", 1)[0]
                    grants = grants.replace("DATABASE " + logical, 'DATABASE "' + database + '"')
                    for role, name in roles.items():
                        grants = grants.replace(':"' + role + '_user"', '"' + name + '"')
                    conn.execute(grants)
                    for role, role_name in roles.items():
                        expected = role != "auth" if logical == "rentals" else role == "auth"
                        assert conn.execute("SELECT has_database_privilege(%s, %s, 'CONNECT')", (role_name, database)).fetchone()[0] == expected
                    if logical == "rentals":
                        conn.execute("""INSERT INTO listings
                            (id,title,description,city,district,region,address,area_m2,rooms,rent_pln,
                             advertiser_type,property_type,status,amenities,images,risk_flags,risk_score,
                             is_demo,first_seen,last_seen,updated_at)
                            VALUES ('listing','t','d','c','d','r','a',50,2,4500,'private',
                                    'apartment','active','[]','[]','[]',0,false,now(),now(),now());
                            INSERT INTO notifications
                            (id,user_id,listing_id,dedupe_key,kind,title,rent_pln,created_at)
                            VALUES ('notice','user','listing','dedupe','new_match','private title',4500,now());
                            INSERT INTO email_subscriptions (user_id,email,enabled,requested_at,unsubscribe_token)
                            VALUES ('user','private@example.invalid',true,now(),'unsubscribe');
                            INSERT INTO email_deliveries
                            (id,user_id,notification_id,confirmation_token,status,attempts,next_attempt_at,claim_token,lease_until)
                            VALUES ('email','user','notice','private-token','pending',0,now(),'lease',now());
                            INSERT INTO push_subscriptions (id,user_id,kind,data,active,created_at)
                            VALUES ('subscription','user','web','{}',true,now());
                            INSERT INTO push_deliveries
                            (id,notification_id,subscription_id,status,attempts,next_attempt_at,claim_token,lease_until)
                            VALUES ('push','notice','subscription','pending',0,now(),'lease',now());""")
                        # Invoke the same SQLAlchemy operation used by Dataflow delisting.
                        engine = create_engine(url.rsplit("/", 1)[0] + "/" + database)
                        try:
                            with Session(engine) as session:
                                session.execute(text('SET ROLE "' + roles["dataflow"] + '"'))
                                cancel_notifications(session, listing_id="listing")
                                session.commit()
                            assert conn.execute("SELECT status, claim_token, lease_until, confirmation_token FROM email_deliveries WHERE id='email'").fetchone() == ("cancelled", None, None, None)
                            assert conn.execute("SELECT status, claim_token, lease_until FROM push_deliveries WHERE id='push'").fetchone() == ("cancelled", None, None)
                            _assert_retention_permissions(engine, conn, roles["indexer"], record, monkeypatch)
                        finally:
                            engine.dispose()
                        assert conn.execute("SELECT status, claim_token, lease_until, confirmation_token FROM email_deliveries WHERE id='email'").fetchone() == ("cancelled", None, None, None)
                        assert conn.execute("SELECT status, claim_token, lease_until FROM push_deliveries WHERE id='push'").fetchone() == ("cancelled", None, None)
                    statements = {
                        "rentals": [("api", "INSERT INTO account_closures (user_id) VALUES ('closed')", True),
                                    ("api", "SELECT * FROM account_closures WHERE user_id='closed'", True),
                                    ("api", "UPDATE account_closures SET user_id='other' WHERE user_id='closed'", False),
                                    ("api", "DELETE FROM account_closures WHERE user_id='closed'", False),
                                    ("api", "SELECT * FROM collection_fetch_state", False),
                                    ("api", "DELETE FROM listing_aliases WHERE false", True),
                                    ("indexer", "SELECT * FROM search_revisions FOR UPDATE", True),
                                    ("indexer", "SELECT confirmation_token FROM email_deliveries", False),
                                    ("indexer", "SELECT user_id FROM email_deliveries", False),
                                    ("indexer", "SELECT title FROM notifications", False),
                                    ("indexer", "UPDATE source_listings SET url=url WHERE false", False),
                                    ("indexer", "DELETE FROM listings WHERE false", False),
                                    ("dataflow", "SELECT confirmation_token FROM email_deliveries", False),
                                    ("dataflow", "SELECT user_id FROM email_deliveries", False),
                                    ("dataflow", "SELECT subscription_id FROM push_deliveries", False),
                                    ("dataflow", "SELECT title FROM notifications", False),
                                    ("dataflow", "DELETE FROM listings WHERE false", False),
                                    ("alerts", "SELECT * FROM account_closures", False),
                                    ("indexer", "SELECT * FROM account_closures", False),
                                    ("dataflow", "SELECT * FROM account_closures", False),
                                    ("auth", "SELECT * FROM listings", False)],
                        "auth": [("api", "SELECT * FROM users", False), ("auth", "SELECT * FROM users", True)],
                    }
                    for role, statement, allowed in statements[logical]:
                        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(roles[role])))
                        try:
                            conn.execute(statement)
                        except psycopg.errors.InsufficientPrivilege:
                            assert not allowed, (role, statement)
                        else:
                            assert allowed, (role, statement)
                        finally:
                            conn.execute("RESET ROLE")
        finally:
            for database in databases.values():
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
            for role in roles.values():
                admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))


def _assert_retention_permissions(engine, conn, role, record, monkeypatch):
    """Exercise the chart's shared indexer/retention identity with real data."""
    from realtoruch import worker
    from realtoruch.ingest import ingest
    from realtoruch.models import AlertEvent, Listing, Outbox, SearchRevision, SourceListing, now

    with Session(engine) as session:
        # A pooled connection used for Dataflow above retains SET ROLE across
        # commits. Reset as the schema owner before constructing the fixture.
        session.execute(text("RESET ROLE"))
        listing_id = ingest(session, record.model_copy(update={
            "external_id": "retention-role-fixture",
            "observed_at": now() - timedelta(days=120),
        }))["listing_id"]
        session.flush()
        session.execute(delete(Outbox).where(Outbox.listing_id == listing_id))
        session.execute(delete(SearchRevision).where(SearchRevision.listing_id == listing_id))
        session.execute(delete(AlertEvent).where(AlertEvent.listing_id == listing_id))
        session.commit()
    conn.execute("UPDATE notifications SET listing_id=%s WHERE id='notice'", (listing_id,))
    conn.execute("UPDATE email_deliveries SET status='pending', claim_token='retention-lease', lease_until=now(), confirmation_token='private-token' WHERE id='email'")
    conn.execute("UPDATE push_deliveries SET status='pending', claim_token='retention-lease', lease_until=now() WHERE id='push'")
    with engine.connect() as maintenance:
        maintenance.execute(text('SET ROLE "' + role + '"'))
        maintenance.commit()
        try:
            with monkeypatch.context() as patch:
                patch.setattr(worker, "Session", sessionmaker(maintenance, expire_on_commit=False))
                worker.retention()
                worker.retention()
        finally:
            maintenance.rollback()
            maintenance.execute(text("RESET ROLE"))
            maintenance.commit()
    with Session(engine) as session:
        source = session.scalar(select(SourceListing).where(SourceListing.listing_id == listing_id))
        assert source.phone_hash is None and source.data["phone_hash"] is None
        assert source.status == source.data["status"] == "unknown"
        assert session.get(Listing, listing_id).status == "unknown"
        assert session.get(SearchRevision, listing_id).revision == 1
        assert len(session.scalars(select(Outbox).where(Outbox.listing_id == listing_id)).all()) == 1
        assert len(session.scalars(select(AlertEvent).where(AlertEvent.listing_id == listing_id)).all()) == 1
