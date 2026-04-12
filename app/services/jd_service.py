import logging
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.job_agent import (
    build_job_analysis_agent,
    build_job_analysis_stream_messages,
    llm_available,
    stream_chat_completion,
)
from app.config import settings
from app.exceptions import DatabaseError, ModelInvocationError, NotFoundError
from app.models import JobDescription
from app.schemas import JobCreate, JobUpdate
from app.services.llm_output_service import normalize_model_output, normalize_streaming_content
from app.tools.jd_tools import detect_focus_areas, extract_keywords, summarize_job

logger = logging.getLogger("findgoodjob.jd_service")

ANALYSIS_SUMMARY_MARKER = "[分析摘要]"
IMPROVEMENT_ADVICE_MARKER = "[改进建议]"


def list_jobs(db: Session) -> list[JobDescription]:
    try:
        return db.query(JobDescription).order_by(JobDescription.created_at.desc(), JobDescription.id.desc()).all()
    except SQLAlchemyError as exc:
        raise DatabaseError("查询岗位列表失败") from exc


def create_job(db: Session, payload: JobCreate) -> JobDescription:
    job = JobDescription(
        title=payload.title,
        company=payload.company,
        jd_text=payload.jd_text,
        status="created",
    )
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("保存岗位信息失败") from exc
    return job


def update_job(db: Session, job_id: int, payload: JobUpdate) -> JobDescription:
    job = get_job_or_404(db, job_id)
    jd_changed = job.jd_text != payload.jd_text

    job.title = payload.title
    job.company = payload.company
    job.jd_text = payload.jd_text

    if jd_changed:
        job.analysis_result = None
        job.analysis_match_score = None
        job.analysis_improvement_advice = None
        job.analysis_model = None
        job.analyzed_at = None
        job.status = "created"

    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("更新岗位信息失败") from exc
    return job


def delete_job(db: Session, job_id: int) -> None:
    job = get_job_or_404(db, job_id)
    try:
        db.delete(job)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("删除岗位失败") from exc


def get_job_or_404(db: Session, job_id: int) -> JobDescription:
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise NotFoundError("岗位不存在", error_code="job_not_found")
    return job


def _build_job_analysis_fallback(job: JobDescription) -> dict[str, str]:
    keywords = extract_keywords(job.jd_text, top_k=10)
    focus = detect_focus_areas(job.jd_text)
    summary = summarize_job(job.jd_text, max_chars=220)
    focus_text = "、".join(focus)
    analysis_result = normalize_model_output(
        (
            "1. 岗位核心职责\n"
            f"基于 JD 内容，岗位主要围绕以下主题展开：{summary}\n\n"
            "2. 关键技能要求\n"
            f"重点关键词：{', '.join(keywords)}\n"
            f"能力方向：{focus_text}\n\n"
            "3. 加分项\n"
            "具备 Agent、RAG 和工程落地项目经验的候选人会更有竞争力。\n\n"
            "4. 候选人应重点强调的经历\n"
            "强调与目标岗位最相关的项目背景、技术选型、业务结果与量化产出。"
        )
    )
    advice_lines = [
        "在简历中突出与岗位核心职责最相关的项目经历和量化成果。",
        f"围绕 {focus_text} 补充更具体的技术细节和业务价值。",
        "把关键词自然放入项目描述和技能清单，方便招聘方快速识别匹配点。",
    ]
    return {
        "analysis_result": analysis_result,
        "improvement_advice": "\n".join(advice_lines),
    }


def _normalize_improvement_advice(value: object) -> str:
    if isinstance(value, list):
        advice_items = [normalize_model_output(str(item)) for item in value if str(item).strip()]
        if not advice_items:
            raise ValueError("improvement_advice list is empty")
        return "\n".join(advice_items)
    if isinstance(value, str) and value.strip():
        return normalize_model_output(value)
    raise ValueError("improvement_advice is invalid")


def _normalize_analysis_payload(payload: dict) -> dict[str, str]:
    analysis_result = normalize_model_output(str(payload.get("analysis_result", "")))
    if not analysis_result:
        raise ValueError("analysis_result is missing")

    improvement_advice = _normalize_improvement_advice(payload.get("improvement_advice"))
    return {
        "analysis_result": analysis_result,
        "improvement_advice": improvement_advice,
    }


def _format_streaming_output(payload: dict[str, str]) -> str:
    return (
        f"{ANALYSIS_SUMMARY_MARKER}\n"
        f"{payload['analysis_result'].strip()}\n\n"
        f"{IMPROVEMENT_ADVICE_MARKER}\n"
        f"{payload['improvement_advice'].strip()}"
    )


def parse_analysis_stream_output(text: str) -> dict[str, str]:
    normalized = normalize_model_output(text).replace("\r\n", "\n")
    summary_index = normalized.find(ANALYSIS_SUMMARY_MARKER)
    advice_index = normalized.find(IMPROVEMENT_ADVICE_MARKER)
    if summary_index == -1 or advice_index == -1:
        raise ValueError("analysis stream markers are missing")

    summary_start = summary_index + len(ANALYSIS_SUMMARY_MARKER)
    analysis_result = normalized[summary_start:advice_index].strip()
    improvement_advice = normalized[advice_index + len(IMPROVEMENT_ADVICE_MARKER) :].strip()
    if not analysis_result or not improvement_advice:
        raise ValueError("analysis stream content is incomplete")
    return {
        "analysis_result": analysis_result,
        "improvement_advice": improvement_advice,
    }


def _chunk_text(text: str, chunk_size: int = 72) -> Iterator[str]:
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]


def _save_analysis_result(
    db: Session,
    job: JobDescription,
    payload: dict[str, str],
    analysis_model: str,
    status: str,
) -> JobDescription:
    job.analysis_result = normalize_model_output(payload["analysis_result"])
    job.analysis_match_score = None
    job.analysis_improvement_advice = normalize_model_output(payload["improvement_advice"])
    job.analysis_model = analysis_model
    job.status = status
    job.analyzed_at = datetime.now(timezone.utc)

    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("保存岗位分析结果失败") from exc
    return job


def analyze_job(db: Session, job: JobDescription) -> JobDescription:
    job_id = getattr(job, "id", "unknown")

    if llm_available():
        try:
            logger.info("job_analysis mode=deepseek job_id=%s model=%s", job_id, settings.deepseek_model)
            agent = build_job_analysis_agent()
            payload = _normalize_analysis_payload(agent.invoke({"input": job.jd_text}))
            analysis_model = settings.deepseek_model
            status = "analyzed"
        except Exception as exc:
            logger.warning("job_analysis mode=fallback job_id=%s reason=%s", job_id, exc)
            payload = _build_job_analysis_fallback(job)
            analysis_model = "fallback"
            status = "analyzed_fallback"
    else:
        logger.warning("job_analysis mode=fallback job_id=%s reason=missing_deepseek_api_key", job_id)
        payload = _build_job_analysis_fallback(job)
        analysis_model = "fallback"
        status = "analyzed_fallback"

    return _save_analysis_result(db, job, payload, analysis_model, status)


async def stream_analyze_job(db: Session, job: JobDescription) -> AsyncIterator[dict]:
    job_id = getattr(job, "id", "unknown")
    yield {"type": "start"}

    if not llm_available():
        logger.warning("job_analysis mode=fallback job_id=%s reason=missing_deepseek_api_key", job_id)
        payload = _build_job_analysis_fallback(job)
        content = _format_streaming_output(payload)
        streamed = ""
        for chunk in _chunk_text(content):
            streamed += chunk
            yield {"type": "chunk", "delta": chunk, "content": streamed}
        analyzed_job = _save_analysis_result(db, job, payload, "fallback", "analyzed_fallback")
        yield {
            "type": "complete",
            "content": content,
            "data": {
                "job_id": analyzed_job.id,
                "analysis_result": analyzed_job.analysis_result or "",
                "analysis_improvement_advice": analyzed_job.analysis_improvement_advice,
            },
        }
        return

    logger.info("job_analysis mode=deepseek_stream job_id=%s model=%s", job_id, settings.deepseek_model)
    content = ""
    previous_normalized = ""
    received_chunk = False
    try:
        messages = build_job_analysis_stream_messages(job.jd_text)
        async for chunk in stream_chat_completion(messages, max_tokens=900):
            received_chunk = True
            content += chunk
            normalized_content = normalize_streaming_content(content)
            delta = normalized_content[len(previous_normalized) :] if normalized_content.startswith(previous_normalized) else ""
            previous_normalized = normalized_content
            yield {"type": "chunk", "delta": delta, "content": normalized_content}
        payload = parse_analysis_stream_output(content)
        analyzed_job = _save_analysis_result(db, job, payload, settings.deepseek_model, "analyzed")
        yield {
            "type": "complete",
            "content": _format_streaming_output(payload),
            "data": {
                "job_id": analyzed_job.id,
                "analysis_result": analyzed_job.analysis_result or "",
                "analysis_improvement_advice": analyzed_job.analysis_improvement_advice,
            },
        }
    except Exception as exc:
        if not received_chunk:
            logger.warning("job_analysis mode=fallback job_id=%s reason=%s", job_id, exc)
            payload = _build_job_analysis_fallback(job)
            content = _format_streaming_output(payload)
            streamed = ""
            for chunk in _chunk_text(content):
                streamed += chunk
                yield {"type": "chunk", "delta": chunk, "content": streamed}
            analyzed_job = _save_analysis_result(db, job, payload, "fallback", "analyzed_fallback")
            yield {
                "type": "complete",
                "content": content,
                "data": {
                    "job_id": analyzed_job.id,
                    "analysis_result": analyzed_job.analysis_result or "",
                    "analysis_improvement_advice": analyzed_job.analysis_improvement_advice,
                },
            }
            return
        raise ModelInvocationError(f"DeepSeek 岗位分析流式输出失败: {exc}") from exc
