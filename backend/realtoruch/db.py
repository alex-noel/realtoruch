from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .settings import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url):
    if get_settings().cloudsql_connection_name and not url.startswith("sqlite"):
        from google.cloud.sql.connector import Connector, IPTypes
        from sqlalchemy.engine import make_url

        parsed = make_url(url)
        connector = Connector(ip_type=IPTypes.PRIVATE, refresh_strategy="LAZY")
        engine = create_engine(
            "postgresql+pg8000://",
            creator=lambda: connector.connect(
                get_settings().cloudsql_connection_name,
                "pg8000",
                user=parsed.username,
                db=parsed.database,
                enable_iam_auth=True,
            ),
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
        )

        @event.listens_for(engine, "engine_disposed")
        def close_connector(_):
            connector.close()

        return engine
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {},
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def sqlite_setup(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = make_engine(get_settings().database_url)
Session = sessionmaker(engine, expire_on_commit=False)


def get_session():
    with Session() as session:
        yield session


def init_db():
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
