import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401
from app.db.database import Base, get_db
from app.main import app
from app.services import llm_service


@pytest.fixture()
def db_session():
    """Fresh in-memory SQLite per test; never touches atlas.db."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Any accidental real LLM call fails loudly instead of hitting the network."""
    def boom(*a, **k):
        raise AssertionError("LLM should not be called here")
    monkeypatch.setattr(llm_service, "generate_response", boom)
