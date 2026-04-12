from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import DatabaseError
from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource, RetrievalLog
from app.schemas import (
    AssistantRagSearchResponse,
    InterviewKnowledgeImportItem,
    InterviewKnowledgeImportResponse,
    InterviewKnowledgeReindexResponse,
    InterviewKnowledgeSearchResponse,
    InterviewKnowledgeSearchResponseItem,
    InterviewKnowledgeSourceListResponse,
    InterviewKnowledgeSourceResponse,
)
from app.services import embedding_service
from app.services.llm_output_service import normalize_model_output

INTERVIEW_CHUNK_SIZE = 520
INTERVIEW_CHUNK_OVERLAP = 120
SUPPORTED_PLATFORM = "xiaohongshu"
INTERVIEW_KNOWLEDGE_JOB_ID = -1
INTERVIEW_SOURCE_TYPE = "manual_summary"
RESEARCH_SOURCE_TYPE = "post"
MANUAL_COMPLIANCE_STATUS = "manual"
RESEARCH_COMPLIANCE_STATUS = "public_research"
VALID_STAGES = {"简历", "笔试", "一面", "二面", "三面", "HR 面", "offer"}


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _remove_noise_lines(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if any(marker in line.lower() for marker in ["私信", "vx", "v信", "加群", "广告", "求捞", "互关"]):
            continue
        lines.append(line)
    return "\n".join(lines)


def _redact_sensitive_content(text: str) -> str:
    redacted = text
    redacted = re.sub(r"1[3-9]\d{9}", "[手机号已脱敏]", redacted)
    redacted = re.sub(r"(微信|vx|V信|wechat)[:：]?\s*[A-Za-z0-9_-]{4,}", r"\1: [已脱敏]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(QQ|qq)[:：]?\s*\d{5,12}", r"\1: [已脱敏]", redacted)
    redacted = re.sub(r"(群|群号)[:：]?\s*\d{5,12}", r"\1: [已脱敏]", redacted)
    return redacted


def _normalize_tags(tags: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for tag in tags or []:
        cleaned = normalize_model_output(str(tag)).strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _infer_interview_stage(text: str, provided_stage: str | None) -> str | None:
    if provided_stage and provided_stage in VALID_STAGES:
        return provided_stage
    for stage in VALID_STAGES:
        if stage in text:
            return stage
    return None


def _infer_company(item: InterviewKnowledgeImportItem, content_clean: str) -> str | None:
    if item.company:
        return normalize_model_output(item.company)
    if item.title:
        match = re.search(r"(字节|美团|阿里|腾讯|京东|快手|拼多多|小红书|携程|滴滴|百度|网易)", item.title)
        if match:
            return match.group(1)
    match = re.search(r"(字节|美团|阿里|腾讯|京东|快手|拼多多|小红书|携程|滴滴|百度|网易)", content_clean)
    return match.group(1) if match else None


def _infer_role(item: InterviewKnowledgeImportItem, content_clean: str) -> str | None:
    if item.role:
        return normalize_model_output(item.role)
    search_text = f"{item.title or ''}\n{content_clean}"
    for role in ["产品经理", "算法工程师", "后端开发", "前端开发", "运营", "设计", "测试开发", "数据分析"]:
        if role in search_text:
            return role
    return None


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[。！？\n])", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _build_summary(content_clean: str, provided_summary: str | None) -> str:
    if provided_summary and provided_summary.strip():
        return normalize_model_output(provided_summary)
    sentences = _split_sentences(content_clean)
    return normalize_model_output(" ".join(sentences[:3])[:240]) or normalize_model_output(content_clean[:240])


def _classify_quality(content_clean: str, provided_score: int | None) -> int:
    if provided_score is not None:
        return max(0, min(100, int(provided_score)))
    score = 50
    if any(keyword in content_clean for keyword in ["一面", "二面", "HR 面", "offer"]):
        score += 15
    if any(keyword in content_clean for keyword in ["问题", "反问", "准备建议", "挂点", "通过"]):
        score += 15
    if len(content_clean) > 200:
        score += 10
    return min(score, 95)


def _chunk_text(text: str, chunk_size: int = INTERVIEW_CHUNK_SIZE, overlap: int = INTERVIEW_CHUNK_OVERLAP) -> list[str]:
    normalized = normalize_model_output(text)
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    return re.findall(r"[a-z0-9.+#_-]{2,}|[\u4e00-\u9fff]{2,}", lowered)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


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


def _build_clean_content(item: InterviewKnowledgeImportItem) -> str:
    normalized = normalize_model_output(item.content_raw)
    cleaned = _remove_noise_lines(normalized)
    cleaned = _redact_sensitive_content(cleaned)
    return normalize_model_output(cleaned)


def _is_valid_interview_experience(content_clean: str, title: str | None = None) -> bool:
    combined = f"{title or ''}\n{content_clean}"
    strong_signals = ["面试", "面经", "一面", "二面", "三面", "HR 面", "HR面", "offer", "笔试"]
    weak_signals = ["反问", "挂", "通过", "转正", "薪资", "项目复盘", "系统设计"]
    strong_hits = sum(1 for signal in strong_signals if signal in combined)
    weak_hits = sum(1 for signal in weak_signals if signal in combined)
    return strong_hits >= 1 and (weak_hits >= 1 or len(content_clean) >= 30)


def _source_to_response(source: KnowledgeSource) -> InterviewKnowledgeSourceResponse:
    session = source._sa_instance_state.session
    if session is None:
        return InterviewKnowledgeSourceResponse(
            id=source.id,
            source_platform=source.source_platform,
            source_type=source.source_type,
            source_id=source.source_id,
            url=source.url,
            title=source.title,
            author_name=source.author_name,
            published_at=source.published_at.isoformat() if source.published_at else None,
            crawl_at=source.crawl_at.isoformat() if source.crawl_at else None,
            ingest_at=source.ingest_at.isoformat() if source.ingest_at else None,
            company=source.company,
            role=source.role,
            interview_stage=source.interview_stage,
            city=source.city,
            tags=json.loads(source.tags_json) if source.tags_json else [],
            quality_score=source.quality_score,
            compliance_status=source.compliance_status,
            content_clean=source.content_clean,
            content_summary=source.content_summary,
            updated_at=source.updated_at.isoformat() if source.updated_at else None,
            chunk_count=0,
            embedding_ready=False,
        )
    return _source_to_response_with_session(session, source)


def _source_to_response_with_session(db: Session, source: KnowledgeSource) -> InterviewKnowledgeSourceResponse:
    tags = json.loads(source.tags_json) if source.tags_json else []
    source_key = f"interview_source:{source.id}"
    document = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.source_type == "interview_experience", KnowledgeDocument.source_key == source_key)
        .first()
    )
    chunks: list[KnowledgeChunk] = []
    if document is not None:
        chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_document_id == document.id).all()
    chunk_count = len(chunks)
    embedding_ready = chunk_count > 0 and all(bool(chunk.embedding_vector) for chunk in chunks)
    return InterviewKnowledgeSourceResponse(
        id=source.id,
        source_platform=source.source_platform,
        source_type=source.source_type,
        source_id=source.source_id,
        url=source.url,
        title=source.title,
        author_name=source.author_name,
        published_at=source.published_at.isoformat() if source.published_at else None,
        crawl_at=source.crawl_at.isoformat() if source.crawl_at else None,
        ingest_at=source.ingest_at.isoformat() if source.ingest_at else None,
        company=source.company,
        role=source.role,
        interview_stage=source.interview_stage,
        city=source.city,
        tags=tags if isinstance(tags, list) else [],
        quality_score=source.quality_score,
        compliance_status=source.compliance_status,
        content_clean=source.content_clean,
        content_summary=source.content_summary,
        updated_at=source.updated_at.isoformat() if source.updated_at else None,
        chunk_count=chunk_count,
        embedding_ready=embedding_ready,
    )


def _upsert_source_document_and_chunks(db: Session, source: KnowledgeSource) -> None:
    from app.models import KnowledgeBase

    knowledge_base = db.query(KnowledgeBase).filter(KnowledgeBase.job_id == INTERVIEW_KNOWLEDGE_JOB_ID).first()
    if knowledge_base is None:
        raise DatabaseError("面试经验知识库未初始化")
    source_key = f"interview_source:{source.id}"
    existing_document = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.source_type == "interview_experience", KnowledgeDocument.source_key == source_key)
        .first()
    )
    metadata = {
        "source_record_id": source.id,
        "source_platform": source.source_platform,
        "company": source.company,
        "role": source.role,
        "interview_stage": source.interview_stage,
        "city": source.city,
        "compliance_status": source.compliance_status,
        "quality_score": source.quality_score,
        "url": source.url,
        "title": source.title,
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False)
    content = normalize_model_output(f"{source.content_summary}\n\n{source.content_clean}")

    if existing_document is None:
        document = KnowledgeDocument(
            knowledge_base_id=knowledge_base.id,
            job_id=INTERVIEW_KNOWLEDGE_JOB_ID,
            source_type="interview_experience",
            source_key=source_key,
            title=source.title or f"{source.company or '面试经验'} 面经",
            content=content,
            metadata_json=metadata_json,
        )
        db.add(document)
        db.flush()
    else:
        document = existing_document
        document.title = source.title or document.title
        document.content = content
        document.metadata_json = metadata_json
        db.add(document)
        db.flush()
        db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_document_id == document.id).delete()

    chunks = _chunk_text(content)
    embeddings = embedding_service.embed_texts(chunks)

    for index, chunk in enumerate(chunks):
        db.add(
            KnowledgeChunk(
                knowledge_document_id=document.id,
                job_id=INTERVIEW_KNOWLEDGE_JOB_ID,
                chunk_index=index,
                content=chunk,
                embedding_vector=_serialize_vector(embeddings[index]),
                metadata_json=metadata_json,
            )
        )


def _ensure_research_knowledge_base_stub(db: Session) -> None:
    from app.models import JobDescription, KnowledgeBase

    stub_job = db.query(JobDescription).filter(JobDescription.id == INTERVIEW_KNOWLEDGE_JOB_ID).first()
    if stub_job is None:
        stub_job = JobDescription(
            id=INTERVIEW_KNOWLEDGE_JOB_ID,
            title="Interview Knowledge",
            company="FindGoodJob",
            jd_text="Global interview knowledge base",
            status="created",
        )
        db.add(stub_job)
        db.flush()
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.job_id == INTERVIEW_KNOWLEDGE_JOB_ID).first()
    if kb is None:
        kb = KnowledgeBase(job_id=INTERVIEW_KNOWLEDGE_JOB_ID, name="Interview Knowledge Base")
        db.add(kb)
        db.flush()


def import_interview_knowledge(
    db: Session,
    items: list[InterviewKnowledgeImportItem],
    *,
    source_type: str,
    compliance_status: str,
) -> InterviewKnowledgeImportResponse:
    imported_sources: list[KnowledgeSource] = []
    try:
        _ensure_research_knowledge_base_stub(db)
        for item in items:
            content_clean = _build_clean_content(item)
            if not _is_valid_interview_experience(content_clean, item.title):
                continue
            company = _infer_company(item, content_clean)
            role = _infer_role(item, content_clean)
            interview_stage = _infer_interview_stage(content_clean, item.interview_stage)
            tags = _normalize_tags(item.tags)
            summary = _build_summary(content_clean, item.content_summary)
            source = KnowledgeSource(
                source_platform=SUPPORTED_PLATFORM,
                source_type=source_type,
                source_id=item.source_id,
                url=item.url,
                title=normalize_model_output(item.title or ""),
                author_name=normalize_model_output(item.author_name or ""),
                published_at=_parse_optional_datetime(item.published_at),
                crawl_at=_parse_optional_datetime(item.crawl_at),
                company=company,
                role=role,
                interview_stage=interview_stage,
                city=normalize_model_output(item.city or ""),
                tags_json=json.dumps(tags, ensure_ascii=False),
                quality_score=_classify_quality(content_clean, item.quality_score),
                compliance_status=compliance_status,
                content_raw=normalize_model_output(item.content_raw),
                content_clean=content_clean,
                content_summary=summary,
                metadata_json=json.dumps(item.metadata or {}, ensure_ascii=False),
            )
            db.add(source)
            db.flush()
            _upsert_source_document_and_chunks(db, source)
            imported_sources.append(source)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("导入面试经验知识库失败") from exc

    return InterviewKnowledgeImportResponse(
        imported_count=len(imported_sources),
        source_platform=SUPPORTED_PLATFORM,
        compliance_status=compliance_status,
        sources=[_source_to_response_with_session(db, source) for source in imported_sources],
    )


def list_interview_knowledge_sources(db: Session, *, limit: int = 50) -> InterviewKnowledgeSourceListResponse:
    sources = (
        db.query(KnowledgeSource)
        .order_by(KnowledgeSource.updated_at.desc(), KnowledgeSource.ingest_at.desc(), KnowledgeSource.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    total_count = db.query(KnowledgeSource).count()
    return InterviewKnowledgeSourceListResponse(
        total_count=total_count,
        sources=[_source_to_response_with_session(db, source) for source in sources],
    )


def import_manual_knowledge(db: Session, items: list[InterviewKnowledgeImportItem]) -> InterviewKnowledgeImportResponse:
    return import_interview_knowledge(
        db,
        items,
        source_type=INTERVIEW_SOURCE_TYPE,
        compliance_status=MANUAL_COMPLIANCE_STATUS,
    )


def import_xiaohongshu_research_knowledge(
    db: Session,
    items: list[InterviewKnowledgeImportItem],
) -> InterviewKnowledgeImportResponse:
    return import_interview_knowledge(
        db,
        items,
        source_type=RESEARCH_SOURCE_TYPE,
        compliance_status=RESEARCH_COMPLIANCE_STATUS,
    )


def reindex_interview_knowledge(db: Session) -> InterviewKnowledgeReindexResponse:
    try:
        _ensure_research_knowledge_base_stub(db)
        sources = db.query(KnowledgeSource).order_by(KnowledgeSource.id.asc()).all()
        for source in sources:
            _upsert_source_document_and_chunks(db, source)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("重建面试经验知识库向量失败。") from exc

    document_count = db.query(KnowledgeDocument).filter(KnowledgeDocument.job_id == INTERVIEW_KNOWLEDGE_JOB_ID).count()
    chunk_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.job_id == INTERVIEW_KNOWLEDGE_JOB_ID).count()
    return InterviewKnowledgeReindexResponse(
        knowledge_base_job_id=INTERVIEW_KNOWLEDGE_JOB_ID,
        source_count=len(sources),
        document_count=document_count,
        chunk_count=chunk_count,
    )


def _field_matches(expected: str, actual: str, *, exact: bool = False) -> bool:
    normalized_expected = normalize_model_output(expected).strip().lower()
    normalized_actual = normalize_model_output(actual).strip().lower()
    if not normalized_expected:
        return True
    if exact:
        return normalized_actual == normalized_expected
    return (
        normalized_actual == normalized_expected
        or normalized_expected in normalized_actual
        or normalized_actual in normalized_expected
    )


def _matches_filter(source: KnowledgeSource, filters: dict) -> bool:
    for field in ["company", "role", "interview_stage", "city"]:
        expected = normalize_model_output(str(filters.get(field) or "")).strip()
        actual = normalize_model_output(str(getattr(source, field) or "")).strip()
        if field == "interview_stage":
            matched = _field_matches(expected, actual, exact=True)
        else:
            matched = _field_matches(expected, actual, exact=False)
        if expected and not matched:
            return False
    return True


def _logical_source_key(source: KnowledgeSource) -> str:
    normalized_source_id = normalize_model_output(source.source_id or "").strip().lower()
    normalized_url = normalize_model_output(source.url or "").strip().lower()
    normalized_title = normalize_model_output(source.title or "").strip().lower()

    if normalized_source_id:
        return f"source_id:{normalized_source_id}"
    if normalized_url:
        return f"url:{normalized_url}"
    if normalized_title:
        return f"title:{normalized_title}"
    return f"row:{source.id}"


def _log_retrieval(db: Session, query: str, filters: dict, result_count: int) -> None:
    log = RetrievalLog(
        query=query,
        source_platform=SUPPORTED_PLATFORM,
        filters_json=json.dumps(filters, ensure_ascii=False),
        result_count=result_count,
    )
    db.add(log)
    db.flush()


def search_interview_knowledge(
    db: Session,
    query: str,
    *,
    company: str | None = None,
    role: str | None = None,
    interview_stage: str | None = None,
    city: str | None = None,
    top_k: int = 4,
) -> InterviewKnowledgeSearchResponse:
    filters = {
        "company": company,
        "role": role,
        "interview_stage": interview_stage,
        "city": city,
    }
    query_vector = embedding_service.embed_text(query)
    chunk_rows = []
    documents = db.query(KnowledgeDocument).filter(KnowledgeDocument.source_type == "interview_experience").all()
    for document in documents:
        if not document.source_key or not document.source_key.startswith("interview_source:"):
            continue
        try:
            source_id = int(document.source_key.split(":")[-1])
        except ValueError:
            continue
        source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
        if source is None:
            continue
        chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_document_id == document.id).all()
        for chunk in chunks:
            chunk_rows.append((chunk, document, source))

    best_results_by_source: dict[str, InterviewKnowledgeSearchResponseItem] = {}
    for chunk, _document, source in chunk_rows:
        if not _matches_filter(source, filters):
            continue
        score = _cosine_similarity(query_vector, _deserialize_vector(chunk.embedding_vector))
        aggregated_score = round(score + (float(source.quality_score or 0) / 1000.0), 6)
        candidate = InterviewKnowledgeSearchResponseItem(
            source_record_id=source.id,
            source_platform=source.source_platform,
            source_type=source.source_type,
            source_id=source.source_id,
            url=source.url,
            title=source.title,
            company=source.company,
            role=source.role,
            interview_stage=source.interview_stage,
            city=source.city,
            content_summary=source.content_summary,
            chunk_text=chunk.content,
            score=aggregated_score,
            compliance_status=source.compliance_status,
        )
        logical_key = _logical_source_key(source)
        existing = best_results_by_source.get(logical_key)
        if existing is None or candidate.score > existing.score:
            best_results_by_source[logical_key] = candidate

    results = list(best_results_by_source.values())
    results.sort(key=lambda item: item.score, reverse=True)
    trimmed = results[:top_k]
    try:
        _log_retrieval(db, query, filters, len(trimmed))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("记录检索日志失败") from exc
    return InterviewKnowledgeSearchResponse(query=query, result_count=len(trimmed), results=trimmed)


def build_interview_rag_context(
    db: Session,
    query: str,
    *,
    company: str | None = None,
    role: str | None = None,
    interview_stage: str | None = None,
    city: str | None = None,
    top_k: int = 4,
) -> str:
    search_result = search_interview_knowledge(
        db,
        query,
        company=company,
        role=role,
        interview_stage=interview_stage,
        city=city,
        top_k=top_k,
    )
    return format_interview_rag_context(search_result)


def format_interview_rag_context(search_result: InterviewKnowledgeSearchResponse) -> str:
    if not search_result.results:
        return "暂无足够的小红书面试经验样本。"

    lines = []
    for item in search_result.results:
        lines.append(f"[来源: {item.source_platform} | {item.company or '未知公司'} | {item.role or '未知岗位'} | {item.interview_stage or '未知轮次'}]")
        if item.url:
            lines.append(f"链接: {item.url}")
        lines.append(f"摘要: {item.content_summary}")
        lines.append(f"片段: {item.chunk_text}")
        lines.append("")
    return "\n".join(lines).strip()


def collect_interview_source_links(search_result: InterviewKnowledgeSearchResponse, *, top_k: int = 3) -> list[str]:
    links: list[str] = []
    for item in search_result.results:
        if item.url and item.url not in links:
            links.append(item.url)
        if len(links) >= top_k:
            break
    return links


def assistant_rag_search(
    db: Session,
    message: str,
    *,
    company: str | None = None,
    role: str | None = None,
    interview_stage: str | None = None,
    city: str | None = None,
    top_k: int = 4,
) -> AssistantRagSearchResponse:
    search_response = search_interview_knowledge(
        db,
        message,
        company=company,
        role=role,
        interview_stage=interview_stage,
        city=city,
        top_k=top_k,
    )
    context = format_interview_rag_context(search_response)
    return AssistantRagSearchResponse(
        message=message,
        context=context,
        result_count=search_response.result_count,
        results=search_response.results,
    )
