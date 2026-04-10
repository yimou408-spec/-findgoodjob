import logging
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.job_agent import build_job_analysis_agent, llm_available
from app.config import settings
from app.exceptions import DatabaseError, NotFoundError
from app.models import JobDescription
from app.schemas import JobCreate
from app.tools.jd_tools import detect_focus_areas, extract_keywords, summarize_job

logger = logging.getLogger("findgoodjob.jd_service")


def list_jobs(db: Session) -> list[JobDescription]:
    """为前端工作台提供岗位列表，默认按创建时间倒序展示最新岗位。"""
    try:
        return db.query(JobDescription).order_by(JobDescription.created_at.desc(), JobDescription.id.desc()).all()
    except SQLAlchemyError as exc:
        raise DatabaseError("查询岗位列表失败") from exc


def create_job(db: Session, payload: JobCreate) -> JobDescription:
    job = JobDescription(
        title=payload.title,
        company=payload.company,
        source=payload.source,
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


def get_job_or_404(db: Session, job_id: int) -> JobDescription:
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise NotFoundError("岗位不存在", error_code="job_not_found")
    return job


def _build_job_analysis_fallback(job: JobDescription) -> str:
    keywords = extract_keywords(job.jd_text, top_k=10)
    focus = detect_focus_areas(job.jd_text)
    summary = summarize_job(job.jd_text, max_chars=220)
    focus_text = "、".join(focus)

    return (
        "1. 岗位核心职责\n"
        f"- 基于 JD 内容，岗位主要围绕以下主题展开：{summary}\n\n"
        "2. 关键技能要求\n"
        f"- 重点关键词：{', '.join(keywords)}\n"
        f"- 能力方向：{focus_text}\n\n"
        "3. 加分项\n"
        "- 具备 Agent、RAG 和工程落地项目经验的候选人会更有竞争力。\n\n"
        "4. 候选人应重点强调的经历\n"
        "- 强调与目标岗位最相关的项目背景、技术选型、业务结果与量化产出。\n\n"
        "5. 简历优化建议\n"
        f"- 在简历中自然补充这些关键词：{', '.join(keywords[:6])}\n"
        f"- 用项目经历证明你在 {focus_text} 上的实际能力。"
    )


def analyze_job(db: Session, job: JobDescription) -> str:
    job_id = getattr(job, "id", "unknown")

    if llm_available():
        logger.info("job_analysis mode=deepseek job_id=%s model=%s", job_id, settings.deepseek_model)
        agent = build_job_analysis_agent()
        result = agent.invoke({"input": job.jd_text})
        analysis = result["output"]
        analysis_model = settings.deepseek_model
        status = "analyzed"
    else:
        logger.warning("job_analysis mode=fallback job_id=%s reason=missing_deepseek_api_key", job_id)
        analysis = _build_job_analysis_fallback(job)
        analysis_model = "fallback"
        status = "analyzed_fallback"

    job.analysis_result = analysis
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
    return analysis
