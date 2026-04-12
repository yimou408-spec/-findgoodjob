import pytest

from app.exceptions import ModelInvocationError
from app.services import embedding_service


pytestmark = pytest.mark.real_embedding_service


def test_embed_texts_batches_requests(monkeypatch):
    captured_batches: list[list[str]] = []

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_request_embeddings(_client, texts):
        captured_batches.append(texts)
        return [[float(index + 1)] * 3 for index, _text in enumerate(texts)]

    monkeypatch.setattr(embedding_service, "zhipu_embedding_available", lambda: True)
    monkeypatch.setattr(embedding_service, "_build_client", lambda: DummyClient())
    monkeypatch.setattr(embedding_service, "_request_embeddings", fake_request_embeddings)

    texts = [f"text-{index}" for index in range(70)]
    embeddings = embedding_service.embed_texts(texts)

    assert len(captured_batches) == 2
    assert len(captured_batches[0]) == 64
    assert len(captured_batches[1]) == 6
    assert len(embeddings) == 70


def test_embed_texts_requires_api_key(monkeypatch):
    monkeypatch.setattr(embedding_service, "zhipu_embedding_available", lambda: False)

    with pytest.raises(ModelInvocationError) as exc_info:
        embedding_service.embed_texts(["hello"])

    assert exc_info.value.error_code == "embedding_unavailable"


def test_embed_texts_rejects_empty_input():
    with pytest.raises(ModelInvocationError) as exc_info:
        embedding_service.embed_texts(["   "])

    assert exc_info.value.error_code == "embedding_invalid_input"
