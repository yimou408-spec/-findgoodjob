from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import DatabaseError
from app.models import JobDescription, KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.services import embedding_service
from app.services.llm_output_service import normalize_model_output
from app.services.resume_service import get_latest_resume_revision

MAX_CHUNK_CHARS = 420
CHUNK_OVERLAP_CHARS = 80
DEFAULT_RETRIEVAL_TOP_K = 4
SOURCE_ORDER = {
    "job_analysis": 4,
    "resume_revision": 3,
    "job_jd": 2,
    "workspace_summary": 1,
}


@dataclass
class KnowledgeStats:
    knowledge_base_id: int
    job_id: int
    document_count: int
    chunk_count: int


def _normalize_document_content(content: str) -> str:
    return normalize_model_output(content).strip()


def _chunk_document_text(text: str, chunk_size: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(length, start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _tokenize_query(query: str) -> list[str]:
    lowered = query.lower()
    terms = re.findall(r"[a-z0-9.+#_-]{2,}|[\u4e00-\u9fff]{2,}", lowered)
    unique_terms: list[str] = []
    for term in terms:
        if term not in unique_terms:
            unique_terms.append(term)
    if lowered.strip() and lowered.strip() not in unique_terms:
        unique_terms.append(lowered.strip())
    return unique_terms[:10]


def _score_chunk_content(content: str, terms: list[str]) -> int:
    lowered = content.lower()
    score = 0
    for term in terms:
        if term and term in lowered:
            score += 1 + lowered.count(term)
    return score


def _serialize_vector(vector: list[float]) -> str:
    return json.dumps(vector, ensure_ascii=False)


def _deserialize_vector(value: str | None) -> list[float]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [float(item) for item in parsed]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def get_or_create_knowledge_base(db: Session, job: JobDescription) -> KnowledgeBase:
    try:
        knowledge_base = db.query(KnowledgeBase).filter(KnowledgeBase.job_id == job.id).first()
        if knowledge_base:
            return knowledge_base

        knowledge_base = KnowledgeBase(job_id=job.id, name=f"{job.title} Knowledge Base")
        db.add(knowledge_base)
        db.commit()
        db.refresh(knowledge_base)
        return knowledge_base
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("创建岗位知识库失败") from exc


def _replace_document_chunks(
    db: Session,
    knowledge_base: KnowledgeBase,
    job_id: int,
    source_type: str,
    title: str,
    content: str,
    source_key: str | None = None,
    metadata: dict | None = None,
) -> None:
    normalized_content = _normalize_document_content(content)
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
    existing = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.knowledge_base_id == knowledge_base.id,
            KnowledgeDocument.source_type == source_type,
            KnowledgeDocument.source_key == source_key,
        )
        .first()
    )

    if not normalized_content:
        if existing is not None:
            db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_document_id == existing.id).delete()
            db.delete(existing)
        return

    if existing is None:
        existing = KnowledgeDocument(
            knowledge_base_id=knowledge_base.id,
            job_id=job_id,
            source_type=source_type,
            source_key=source_key,
            title=title,
            content=normalized_content,
            metadata_json=metadata_json,
        )
        db.add(existing)
        db.flush()
    else:
        existing.title = title
        existing.content = normalized_content
        existing.metadata_json = metadata_json
        db.add(existing)
        db.flush()
        db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_document_id == existing.id).delete()

    chunks = _chunk_document_text(normalized_content)
    embeddings = embedding_service.embed_texts(chunks)

    for index, chunk in enumerate(chunks):
        db.add(
            KnowledgeChunk(
                knowledge_document_id=existing.id,
                job_id=job_id,
                chunk_index=index,
                content=chunk,
                embedding_vector=_serialize_vector(embeddings[index]),
                metadata_json=metadata_json,
            )
        )


def index_job_workspace(db: Session, job: JobDescription) -> KnowledgeStats:
    knowledge_base = get_or_create_knowledge_base(db, job)
    latest_revision = get_latest_resume_revision(db, job.id)

    try:
        _replace_document_chunks(
            db,
            knowledge_base,
            job.id,
            source_type="job_jd",
            source_key="current",
            title=f"{job.title} JD",
            content=job.jd_text,
            metadata={"company": job.company},
        )
        _replace_document_chunks(
            db,
            knowledge_base,
            job.id,
            source_type="job_analysis",
            source_key="current",
            title=f"{job.title} Analysis",
            content="\n\n".join(
                value
                for value in [job.analysis_result or "", job.analysis_improvement_advice or ""]
                if value and value.strip()
            ),
            metadata={"analysis_model": job.analysis_model},
        )
        if latest_revision is not None:
            _replace_document_chunks(
                db,
                knowledge_base,
                job.id,
                source_type="resume_revision",
                source_key=str(latest_revision.id),
                title=f"{job.title} Resume Revision",
                content="\n\n".join(
                    [
                        latest_revision.source_resume_text.strip(),
                        latest_revision.revised_resume.strip(),
                        latest_revision.match_explanation or "",
                    ]
                ),
                metadata={"match_score": latest_revision.match_score},
            )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("更新岗位知识库失败") from exc

    return get_job_knowledge_stats(db, job.id)


def get_job_knowledge_stats(db: Session, job_id: int) -> KnowledgeStats:
    knowledge_base = db.query(KnowledgeBase).filter(KnowledgeBase.job_id == job_id).first()
    if knowledge_base is None:
        return KnowledgeStats(knowledge_base_id=0, job_id=job_id, document_count=0, chunk_count=0)

    try:
        document_count = db.query(KnowledgeDocument).filter(KnowledgeDocument.job_id == job_id).count()
        chunk_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.job_id == job_id).count()
    except SQLAlchemyError as exc:
        raise DatabaseError("查询岗位知识库统计失败") from exc

    return KnowledgeStats(
        knowledge_base_id=knowledge_base.id,
        job_id=job_id,
        document_count=document_count,
        chunk_count=chunk_count,
    )


def retrieve_job_knowledge(db: Session, job_id: int, query: str, top_k: int = DEFAULT_RETRIEVAL_TOP_K) -> list[KnowledgeChunk]:
    try:
        chunks = (
            db.query(KnowledgeChunk, KnowledgeDocument.source_type)
            .join(KnowledgeDocument, KnowledgeChunk.knowledge_document_id == KnowledgeDocument.id)
            .filter(KnowledgeChunk.job_id == job_id)
            .all()
        )
    except SQLAlchemyError as exc:
        raise DatabaseError("检索岗位知识片段失败") from exc

    if not chunks:
        return []

    query_vector = embedding_service.embed_text(query)
    ranked: list[tuple[float, int, KnowledgeChunk]] = []
    for chunk, source_type in chunks:
        score = _cosine_similarity(query_vector, _deserialize_vector(chunk.embedding_vector))
        source_boost = SOURCE_ORDER.get(source_type, 0)
        ranked.append((score, source_boost, chunk))

    ranked.sort(key=lambda item: (item[0], item[1], -item[2].chunk_index), reverse=True)
    matched = [chunk for score, _boost, chunk in ranked if score > 0]
    if matched:
        return matched[:top_k]
    return [chunk for _score, _boost, chunk in ranked[:top_k]]


def build_retrieval_context(db: Session, job_id: int, query: str, top_k: int = DEFAULT_RETRIEVAL_TOP_K) -> str:
    chunks = retrieve_job_knowledge(db, job_id, query, top_k=top_k)
    if not chunks:
        return "暂无可用知识库片段。"

    lines = []
    for chunk in chunks:
        document = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == chunk.knowledge_document_id).first()
        title = document.title if document is not None else "Knowledge"
        lines.append(f"[{title} - chunk {chunk.chunk_index + 1}]")
        lines.append(chunk.content.strip())
        lines.append("")
    return "\n".join(lines).strip()
