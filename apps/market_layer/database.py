from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./market_layer.db"


Base = declarative_base()


def build_engine(database_url: str = DEFAULT_DATABASE_URL):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def build_session_factory(database_url: str = DEFAULT_DATABASE_URL):
    engine = build_engine(database_url)
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def get_db(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
