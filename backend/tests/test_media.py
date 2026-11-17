"""Synthetic owner media lifecycle and validation."""
import io
import os
from uuid import uuid4
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from realtoruch.api import app, erase_account_data
from realtoruch.db import Base, get_session
from realtoruch.models import MediaAsset, now
from realtoruch.security import require_claims
from realtoruch.settings import get_settings


@pytest.fixture(params=["sqlite", "postgres"])
def media_client(request, tmp_path, monkeypatch):
    admin = None
    if request.param == "sqlite":
        engine = create_engine("sqlite:///" + str(tmp_path / "media.db"), connect_args={"check_same_thread": False})
    else:
        if not os.environ.get("TEST_POSTGRES_URL"):
            pytest.skip("requires isolated PostgreSQL")
        schema = "t23_" + uuid4().hex
        admin = create_engine(os.environ["TEST_POSTGRES_URL"], isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        engine = create_engine(os.environ["TEST_POSTGRES_URL"], connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    settings = get_settings()
    monkeypatch.setattr(settings, "media_storage_backend", "local")
    monkeypatch.setattr(settings, "media_directory", str(tmp_path / "objects"))
    def session_dependency():
        with factory() as session:
            yield session
    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[require_claims] = lambda: {"sub": "one", "email_verified": True}
    with TestClient(app) as client:
        yield client, factory, tmp_path
    app.dependency_overrides.clear()
    engine.dispose()
    if admin:
        with admin.connect() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def picture(fmt="JPEG", exif=None, size=(40, 20)):
    data = io.BytesIO()
    Image.new("RGB", size, (240, 2, 3)).save(data, format=fmt, exif=exif or b"")
    return data.getvalue()


def upload(client, key, data=None, mime="image/jpeg"):
    return client.post("/v1/me/media", content=data or picture(), headers={"Idempotency-Key": key, "Content-Type": mime})




def test_upload_retry_private_preview_and_cancel(media_client):
    client, factory, path = media_client
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private metadata"
    original = picture(exif=exif)
    response = upload(client, "first", original)
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["state"] == "ready"
    assert upload(client, "first", original).json()["id"] == item["id"]
    assert upload(client, "first", picture(size=(10, 10))).status_code == 409
    image = Image.open(io.BytesIO(client.get(item["display_url"]).content))
    assert image.size == (20, 40) and not image.getexif()
    assert client.get("/v1/media/" + item["id"] + "/display").status_code == 404
    assert client.delete("/v1/me/media/" + item["id"]).json()["state"] == "deleted"
    assert client.get(item["display_url"]).status_code == 404
    assert not list((path / "objects").rglob("a"))
    assert client.delete("/v1/me/media/by-key/early").status_code == 200
    assert upload(client, "early").status_code == 409


def test_reject_invalid_mismatch_animation_and_oversize(media_client):
    client, _, _ = media_client
    assert upload(client, "mismatch", picture("PNG"), "image/jpeg").status_code == 415
    assert upload(client, "svg", b"<svg/>", "image/svg+xml").status_code == 415
    animation = io.BytesIO()
    a = Image.new("RGB", (3, 3), "red")
    a.save(animation, "WEBP", save_all=True, append_images=[Image.new("RGB", (3, 3), "blue")])
    assert upload(client, "animated", animation.getvalue(), "image/webp").status_code == 422
    assert upload(client, "big", b"x" * (10 * 1024 * 1024 + 1)).status_code == 413
    assert upload(client, "pixels", picture("PNG", size=(5000, 4001)), "image/png").status_code == 422
    assert upload(client, "side", picture("PNG", size=(1, 32769)), "image/png").status_code == 422


def test_fake_gcs_adapter():
    from realtoruch.media_storage import GCSStorage
    class Blob:
        def __init__(self, objects, key):
            self.objects, self.key = objects, key
        def upload_from_string(self, value, content_type, if_generation_match, timeout, retry):
            assert timeout == 10 and retry is None
            assert content_type == "image/jpeg" and if_generation_match == 0
            assert self.key not in self.objects
            self.objects[self.key] = value
        def download_as_bytes(self, timeout, retry):
            assert timeout == 10 and retry is None
            return self.objects[self.key]
        def reload(self, timeout, retry):
            assert timeout == 10 and retry is None
            if self.key not in self.objects:
                error = Exception()
                error.code = 404
                raise error
            self.generation = 1
        def delete(self, if_generation_match, timeout, retry):
            assert if_generation_match == 1
            assert timeout == 10 and retry is None
            if self.key not in self.objects:
                error = Exception()
                error.code = 404
                raise error
            del self.objects[self.key]
    class Bucket:
        def __init__(self): self.objects = {}
        def blob(self, key): return Blob(self.objects, key)
    adapter = GCSStorage(Bucket())
    adapter.put("opaque/a", b"synthetic")
    assert adapter.get("opaque/a") == b"synthetic"
    adapter.delete("opaque/a")
    adapter.delete("opaque/a")


def test_media_migration_postgres_upgrade_preserves_rows(tmp_path):
    import json
    from realtoruch.migrations import REGISTRY, apply_postgres
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("requires isolated PostgreSQL")
    schema = "t23_migrate_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    registry = json.loads(REGISTRY.read_text())
    registry["rentals"] = [entry for entry in registry["rentals"] if entry["version"] != "011"]
    old_registry = tmp_path / "old.json"
    old_registry.write_text(json.dumps(registry))
    try:
        with engine.begin() as conn:
            apply_postgres(conn, "rentals", old_registry)
            conn.execute(text("INSERT INTO advertiser_profiles (user_id, name, kind, description, updated_at) VALUES ('existing', 'Canary', 'private', 'keep', CURRENT_TIMESTAMP)"))
        with engine.begin() as conn:
            apply_postgres(conn, "rentals")
            apply_postgres(conn, "rentals")
            assert conn.execute(text("SELECT name, description FROM advertiser_profiles WHERE user_id='existing'")).one() == ("Canary", "keep")
            assert conn.execute(text("SELECT count(*) FROM media_assets")).scalar_one() == 0
            assert conn.execute(text("SELECT count(*) FROM realtoruch_migrations WHERE version='011'")).scalar_one() == 1
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_chunked_stream_cap(media_client):
    client, _, _ = media_client
    def chunks():
        for _ in range(11):
            yield b"x" * (1024 * 1024)
    response = client.post("/v1/me/media", content=chunks(), headers={"Idempotency-Key": "chunks", "Content-Type": "image/jpeg"})
    assert response.status_code == 413
    assert client.get("/v1/me/media/by-key/chunks").json()["state"] == "pending"


def test_local_storage_private_modes_and_symlink_rejection(tmp_path):
    import stat
    from realtoruch.media_storage import LocalStorage
    asset = "12345678-1234-1234-1234-123456789abc"
    root = tmp_path / "private"
    adapter = LocalStorage(root)
    adapter.put(asset + "/a", b"photo")
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE((root / asset).stat().st_mode) == 0o700
    assert stat.S_IMODE((root / asset / "a").stat().st_mode) == 0o600
    (root / asset / "b").symlink_to(tmp_path / "outside")
    with pytest.raises((OSError, ValueError)):
        adapter.get(asset + "/b")
    with pytest.raises((OSError, ValueError)):
        adapter.delete(asset + "/b")


def test_sqlite_media_upgrade_preserves_existing_data(tmp_path):
    from realtoruch.migrations import upgrade_local
    from realtoruch.models import AdvertiserProfile
    engine = create_engine("sqlite:///" + str(tmp_path / "upgrade.db"))
    Base.metadata.create_all(engine)
    upgrade_local(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO advertiser_profiles (user_id,name,kind,description,updated_at) VALUES ('existing','Canary','private','keep',CURRENT_TIMESTAMP)"))
        conn.execute(text("DROP TABLE media_assets"))
        conn.execute(text("DELETE FROM realtoruch_local_migrations WHERE database_name='rentals' AND version='011'"))
    upgrade_local(engine)
    upgrade_local(engine)
    with sessionmaker(engine)() as session:
        assert session.get(AdvertiserProfile, "existing").description == "keep"
        assert session.query(MediaAsset).count() == 0
    engine.dispose()


def test_upload_processing_is_serialized(media_client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock
    from realtoruch import media
    client, _, _ = media_client
    first_started, second_reserved, release = Event(), Event(), Event()
    calls = []
    mutex = Lock()
    original_decode, original_find = media.decode, media.find_key
    def find(session, user, key):
        row = original_find(session, user, key)
        if key == "second":
            second_reserved.set()
        return row
    def decode(data, mime):
        with mutex:
            calls.append(len(calls) + 1)
            number = calls[-1]
        if number == 1:
            first_started.set()
            assert release.wait(10)
        return original_decode(data, mime)
    monkeypatch.setattr(media, "find_key", find)
    monkeypatch.setattr(media, "decode", decode)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(upload, client, "first-serial")
        assert first_started.wait(10)
        assert app.state.media_processors.locked()
        second = pool.submit(upload, client, "second")
        assert second_reserved.wait(10)
        assert calls == [1]
        release.set()
        assert first.result(timeout=10).status_code == 201
        assert second.result(timeout=10).status_code == 201
    assert calls == [1, 2]


@pytest.mark.parametrize("fmt,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_gps_orientation_stripped_in_both_derivatives(media_client, fmt, mime):
    from PIL import TiffImagePlugin
    client, _, _ = media_client
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "synthetic metadata canary"
    gps = exif.get_ifd(34853)
    gps[1] = "N"
    gps[2] = tuple(TiffImagePlugin.IFDRational(v) for v in (50, 0, 0))
    gps[3] = "E"
    gps[4] = tuple(TiffImagePlugin.IFDRational(v) for v in (19, 0, 0))
    exif[34853] = gps
    data = picture(fmt, exif=exif, size=(2500, 1100))
    with Image.open(io.BytesIO(data)) as source:
        assert source.getexif()[274] == 6 and source.getexif().get_ifd(34853)[1] == "N"
    response = upload(client, "gps-" + fmt, data, mime)
    assert response.status_code == 201, response.text
    item = response.json()
    for name, size in (("display_url", (901, 2048)), ("thumbnail_url", (176, 400))):
        response = client.get(item[name])
        assert response.status_code == 200
        with Image.open(io.BytesIO(response.content)) as image:
            assert image.format == "JPEG" and image.size == size and not image.getexif()
            assert not any(key in image.info for key in ("exif", "icc_profile", "xmp", "comment"))


def test_competing_payloads_same_key_do_not_replace_winner(media_client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from realtoruch import media
    client, _, _ = media_client
    entered, reserved, release = Event(), Event(), Event()
    original_decode, original_find = media.decode, media.find_key
    count = 0
    def find(session, user, key):
        nonlocal count
        result = original_find(session, user, key)
        count += 1
        if count == 2:
            reserved.set()
        return result
    def paused(data, mime):
        entered.set()
        assert release.wait(10)
        return original_decode(data, mime)
    monkeypatch.setattr(media, "find_key", find)
    monkeypatch.setattr(media, "decode", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(upload, client, "shared", picture(size=(20, 10)))
        assert entered.wait(10)
        second = pool.submit(upload, client, "shared", picture(size=(10, 20)))
        assert reserved.wait(10)
        release.set()
        winner, loser = first.result(timeout=10), second.result(timeout=10)
    assert winner.status_code == 201 and loser.status_code == 409
    assert client.get("/v1/me/media/by-key/shared").json()["id"] == winner.json()["id"]
    assert Image.open(io.BytesIO(client.get(winner.json()["display_url"]).content)).size == (20, 10)


def test_generation_matched_delete_preserves_newer_object():
    from realtoruch.media_storage import GCSStorage
    class Conflict(Exception):
        code = 412
    class Blob:
        generation = None
        def __init__(self, bucket): self.bucket = bucket
        def reload(self, **kwargs): self.generation = self.bucket.generation
        def delete(self, if_generation_match, **kwargs):
            self.bucket.generation += 1  # A newer create wins after metadata read.
            if if_generation_match != self.bucket.generation:
                raise Conflict()
            self.bucket.content = None
    class Bucket:
        generation, content = 5, b"newer object"
        def blob(self, key): return Blob(self)
    bucket = Bucket()
    with pytest.raises(Conflict):
        GCSStorage(bucket).delete("opaque/a")
    assert bucket.generation == 6 and bucket.content == b"newer object"


def test_disabled_media_and_owner_isolation(media_client, monkeypatch):
    client, _, _ = media_client
    settings = get_settings()
    monkeypatch.setattr(settings, "media_storage_backend", "disabled")
    assert upload(client, "disabled").status_code == 503
    monkeypatch.setattr(settings, "media_storage_backend", "local")
    item = upload(client, "owner-only").json()
    app.dependency_overrides[require_claims] = lambda: {"sub": "other", "email_verified": True}
    assert client.get("/v1/me/media/" + item["id"]).status_code == 403
    assert client.get(item["display_url"]).status_code == 403
    assert client.delete("/v1/me/media/" + item["id"]).status_code == 403
    app.dependency_overrides[require_claims] = lambda: {"sub": "one", "email_verified": False}
    assert client.get("/v1/me/media/" + item["id"]).status_code == 403


def test_closed_account_cannot_manage_media(media_client):
    from realtoruch.models import AccountClosure
    client, factory, _ = media_client
    item = upload(client, "before-closure").json()
    with factory.begin() as session:
        session.add(AccountClosure(user_id="one"))
    assert client.get("/v1/me/media/" + item["id"]).status_code == 401
    assert client.get(item["thumbnail_url"]).status_code == 401
    assert client.delete("/v1/me/media/" + item["id"]).status_code == 401
    assert upload(client, "after-closure").status_code == 401
