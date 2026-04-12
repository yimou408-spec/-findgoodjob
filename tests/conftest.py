import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["ZHIPU_API_KEY"] = ""
os.environ["DATABASE_URL"] = "sqlite://"

from app.database import Base, get_db
from app.main import app
from app.services import embedding_service


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def fake_embedding_backend(monkeypatch, request):
    if request.node.get_closest_marker("real_embedding_service"):
        return

    def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            length_score = float(len(lowered))
            rag_score = 10.0 if "rag" in lowered else 0.0
            ai_score = 10.0 if "ai" in lowered else 0.0
            pm_score = 10.0 if "产品" in lowered else 0.0
            backend_score = 10.0 if "后端" in lowered else 0.0
            growth_score = 10.0 if "增长" in lowered else 0.0
            vectors.append([length_score, rag_score, ai_score, pm_score, backend_score, growth_score])
        return vectors

    monkeypatch.setattr(embedding_service, "zhipu_embedding_available", lambda: True)
    monkeypatch.setattr(embedding_service, "get_embedding_dimensions", lambda: 1024)
    monkeypatch.setattr(embedding_service, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(embedding_service, "embed_text", lambda text: _fake_embed_texts([text])[0])


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
