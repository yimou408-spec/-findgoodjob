from __future__ import annotations

from collections.abc import Iterable

import httpx

from app.config import settings
from app.exceptions import ModelInvocationError
from app.services.llm_output_service import normalize_model_output

MAX_EMBEDDING_BATCH_SIZE = 64


def zhipu_embedding_available() -> bool:
    return bool(settings.zhipu_api_key)


def get_embedding_dimensions() -> int:
    return int(settings.zhipu_embedding_dimensions)


def _build_client() -> httpx.Client:
    return httpx.Client(trust_env=False, timeout=settings.zhipu_embedding_timeout_seconds)


def _normalize_embedding_input(text: str) -> str:
    return normalize_model_output(text).strip()


def _chunk_iterable(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _request_embeddings(client: httpx.Client, texts: list[str]) -> list[list[float]]:
    if not zhipu_embedding_available():
        raise ModelInvocationError("未配置 ZHIPU_API_KEY，无法执行真正的向量检索。", error_code="embedding_unavailable")

    payload = {
        "model": settings.zhipu_embedding_model,
        "input": texts,
        "dimensions": get_embedding_dimensions(),
    }
    headers = {
        "Authorization": f"Bearer {settings.zhipu_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = client.post(settings.zhipu_embedding_base_url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise ModelInvocationError(f"智谱 Embedding 调用失败: {exc}", error_code="embedding_request_failed") from exc

    if response.status_code >= 400:
        detail = response.text
        raise ModelInvocationError(
            f"智谱 Embedding 调用失败: {detail}",
            error_code="embedding_request_failed",
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ModelInvocationError("智谱 Embedding 返回了无法解析的响应。", error_code="embedding_invalid_response") from exc

    rows = data.get("data")
    if not isinstance(rows, list) or not rows:
        raise ModelInvocationError("智谱 Embedding 未返回有效向量。", error_code="embedding_empty_response")

    embeddings: list[list[float]] = []
    for row in rows:
        embedding = row.get("embedding") if isinstance(row, dict) else None
        if not isinstance(embedding, list) or not embedding:
            raise ModelInvocationError("智谱 Embedding 返回了空向量。", error_code="embedding_empty_response")
        embeddings.append([float(item) for item in embedding])
    return embeddings


def embed_texts(texts: list[str]) -> list[list[float]]:
    normalized_texts = [_normalize_embedding_input(text) for text in texts]
    if not normalized_texts:
        return []
    if any(not text for text in normalized_texts):
        raise ModelInvocationError("待向量化文本为空，无法生成 embedding。", error_code="embedding_invalid_input")

    embeddings: list[list[float]] = []
    with _build_client() as client:
        for batch in _chunk_iterable(normalized_texts, MAX_EMBEDDING_BATCH_SIZE):
            embeddings.extend(_request_embeddings(client, batch))
    return embeddings


def embed_text(text: str) -> list[float]:
    embeddings = embed_texts([text])
    if not embeddings:
        raise ModelInvocationError("智谱 Embedding 未返回有效向量。", error_code="embedding_empty_response")
    return embeddings[0]
