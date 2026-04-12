import logging
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.job_agent import build_llm, llm_available, stream_chat_completion
from app.config import settings
from app.exceptions import DatabaseError, ModelInvocationError
from app.models import JobDescription, ResumeRevision
from app.services.llm_output_service import normalize_model_output, normalize_streaming_content
from app.tools.jd_tools import detect_focus_areas, extract_keywords

logger = logging.getLogger("findgoodjob.resume_service")

MAX_RESUME_CHARS_FOR_LLM = 4000
MATCH_SCORE_MARKER = "[匹配度评分]"
MATCH_EXPLANATION_MARKER = "[评分说明]"
REVISED_RESUME_MARKER = "[修订简历]"


@dataclass
class ResumeRevisionResult:
    revised_resume: str
    match_score: int | None = None
    match_explanation: str | None = None


def save_resume_revision_record(
    db: Session,
    job: JobDescription,
    source_resume_text: str,
    result: ResumeRevisionResult,
) -> ResumeRevision:
    record = ResumeRevision(
        job_id=job.id,
        source_resume_text=source_resume_text,
        revised_resume=normalize_model_output(result.revised_resume),
        match_score=result.match_score,
        match_explanation=normalize_model_output(result.match_explanation or ""),
    )
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("保存简历修订记录失败") from exc
    return record


def get_latest_resume_revision(db: Session, job_id: int) -> ResumeRevision | None:
    try:
        return (
            db.query(ResumeRevision)
            .filter(ResumeRevision.job_id == job_id)
            .order_by(ResumeRevision.created_at.desc(), ResumeRevision.id.desc())
            .first()
        )
    except SQLAlchemyError as exc:
        raise DatabaseError("查询最近一次简历修订记录失败") from exc


class ResumeRevisionStructuredOutput(BaseModel):
    match_score: int = Field(description="修订后简历与目标岗位的匹配度评分，0 到 100 的整数")
    match_explanation: str = Field(description="2 到 3 句中文说明，解释为什么是这个匹配度评分")
    revised_resume: str = Field(description="一份可直接使用的中文简历修订结果，突出与岗位最相关的能力与经历")


def _with_max_tokens(llm, max_tokens: int):
    return llm.bind(max_tokens=max_tokens) if hasattr(llm, "bind") else llm


def _normalize_resume_text(resume_text: str) -> str:
    lines = [line.strip() for line in resume_text.replace("\r\n", "\n").split("\n")]
    compact_lines = [line for line in lines if line]
    normalized = "\n".join(compact_lines).strip()
    return normalized or resume_text.strip()


def _trim_resume_text_for_llm(resume_text: str) -> str:
    normalized = _normalize_resume_text(resume_text)
    if len(normalized) <= MAX_RESUME_CHARS_FOR_LLM:
        return normalized

    logger.info(
        "resume_revision truncating_resume_text original_chars=%s trimmed_chars=%s",
        len(normalized),
        MAX_RESUME_CHARS_FOR_LLM,
    )
    return normalized[:MAX_RESUME_CHARS_FOR_LLM].rstrip() + "\n\n[内容因过长已截断]"


def _normalize_match_score(value: int) -> int:
    return max(0, min(100, int(value)))


def _estimate_match_score(keywords: list[str], resume_text: str) -> int:
    normalized_resume = resume_text.lower()
    matched = sum(1 for keyword in keywords if keyword.lower() in normalized_resume)
    if not keywords:
        return 65

    coverage = matched / len(keywords)
    score = 55 + round(coverage * 35)
    return max(45, min(92, score))


def _build_resume_revision_fallback(job: JobDescription, resume_text: str) -> ResumeRevisionResult:
    keywords = extract_keywords(job.jd_text, top_k=8)
    focus = detect_focus_areas(job.jd_text)
    focus_text = "、".join(focus)
    missing_keywords = [keyword for keyword in keywords if keyword.lower() not in resume_text.lower()][:5]
    match_score = _estimate_match_score(keywords, resume_text)
    match_explanation = normalize_model_output(
        (
            f"评分基于当前简历对岗位关键词和重点方向的覆盖情况生成。"
            f"当前重点关注 {focus_text}。"
            f"明显缺失的关键词包括：{', '.join(missing_keywords) if missing_keywords else '暂无明显缺失'}。"
        )
    )
    revised_resume = normalize_model_output(
        (
            "1. 岗位匹配度判断\n"
            f"当前简历与目标岗位《{job.title}》存在基础匹配，但需要更突出与岗位直接相关的经验。\n\n"
            "2. 关键差距\n"
            f"当前简历对以下关键词体现不足：{', '.join(missing_keywords) if missing_keywords else '暂无明显缺失'}\n"
            f"岗位重点方向包括：{focus_text}\n\n"
            "3. 优化建议\n"
            f"在项目经历中补充与 {focus_text} 相关的具体实践\n"
            "使用结果导向语言描述技能与产出\n"
            f"将以下关键词自然融入简历：{', '.join(keywords)}\n\n"
            "4. 修订后的简历文本\n"
            f"{resume_text}\n\n"
            "建议重写方向：\n"
            f"应突出与 {job.title} 最相关的项目、技术栈和业务成果，并保持内容真实可验证。"
        )
    )
    return ResumeRevisionResult(
        revised_resume=revised_resume,
        match_score=match_score,
        match_explanation=match_explanation,
    )


def _coerce_structured_result(parsed: ResumeRevisionStructuredOutput) -> ResumeRevisionResult:
    revised_resume = normalize_model_output(parsed.revised_resume)
    if not revised_resume:
        raise ValueError("revised_resume is empty")

    match_explanation = normalize_model_output(parsed.match_explanation)
    if not match_explanation:
        raise ValueError("match_explanation is empty")

    return ResumeRevisionResult(
        revised_resume=revised_resume,
        match_score=_normalize_match_score(parsed.match_score),
        match_explanation=match_explanation,
    )


def _extract_parse_diagnostics(raw_result: dict) -> str:
    parsing_error = raw_result.get("parsing_error")
    raw_message = raw_result.get("raw")
    parsed = raw_result.get("parsed")

    diagnostics: list[str] = []
    if parsing_error:
        diagnostics.append(f"parsing_error={parsing_error}")

    if raw_message is not None:
        response_metadata = getattr(raw_message, "response_metadata", {}) or {}
        finish_reason = response_metadata.get("finish_reason")
        if finish_reason:
            diagnostics.append(f"finish_reason={finish_reason}")

        token_usage = response_metadata.get("token_usage")
        if token_usage:
            diagnostics.append(f"token_usage={token_usage}")

        content = getattr(raw_message, "content", "")
        if isinstance(content, str) and content.strip():
            preview = normalize_model_output(content).replace("\n", " ")
            diagnostics.append(f"raw_preview={preview[:240]}")

    if parsed is not None:
        diagnostics.append(f"parsed_type={type(parsed).__name__}")

    return "; ".join(diagnostics) or "no diagnostics available"


def _format_streaming_output(result: ResumeRevisionResult) -> str:
    return (
        f"{MATCH_SCORE_MARKER}\n"
        f"{result.match_score if result.match_score is not None else '--'}\n\n"
        f"{MATCH_EXPLANATION_MARKER}\n"
        f"{normalize_model_output(result.match_explanation or '')}\n\n"
        f"{REVISED_RESUME_MARKER}\n"
        f"{normalize_model_output(result.revised_resume)}"
    )


def parse_resume_stream_output(text: str) -> ResumeRevisionResult:
    normalized = normalize_model_output(text).replace("\r\n", "\n")
    score_index = normalized.find(MATCH_SCORE_MARKER)
    explanation_index = normalized.find(MATCH_EXPLANATION_MARKER)
    revised_index = normalized.find(REVISED_RESUME_MARKER)
    if score_index == -1 or explanation_index == -1 or revised_index == -1:
        raise ValueError("resume stream markers are missing")

    score_block = normalized[score_index + len(MATCH_SCORE_MARKER) : explanation_index].strip()
    explanation = normalized[explanation_index + len(MATCH_EXPLANATION_MARKER) : revised_index].strip()
    revised_resume = normalized[revised_index + len(REVISED_RESUME_MARKER) :].strip()

    score_line = next((line.strip() for line in score_block.splitlines() if line.strip()), "")
    score = int(score_line)
    if not explanation or not revised_resume:
        raise ValueError("resume stream content is incomplete")

    return ResumeRevisionResult(
        revised_resume=normalize_model_output(revised_resume),
        match_score=_normalize_match_score(score),
        match_explanation=normalize_model_output(explanation),
    )


def build_resume_revision_stream_messages(job: JobDescription, resume_text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是一名资深求职顾问。请一般情况下使用中文自然表达，"
                "但遇到英文书名、网站名、产品名、框架名、模型名、技术术语或行业通用专有名词时保留原文。"
                "请严格按下面结构返回，不要添加任何额外前言、解释或结尾，也不要使用 Markdown 强调、星号列表或井号标题。\n"
                "[匹配度评分]\n"
                "只输出一个 0 到 100 的整数。\n\n"
                "[评分说明]\n"
                "用 2 到 3 句话说明当前简历与岗位的匹配情况。\n\n"
                "[修订简历]\n"
                "输出修订后的完整简历文本。请只基于用户原简历做增强，不得编造不存在的经历。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"目标岗位：{job.title}\n"
                f"公司：{job.company}\n"
                f"岗位 JD：\n{job.jd_text}\n\n"
                f"岗位分析：\n{job.analysis_result or '暂无岗位分析，请基于 JD 自行判断。'}\n\n"
                f"原始简历：\n{resume_text}"
            ),
        },
    ]


def _chunk_text(text: str, chunk_size: int = 72) -> Iterator[str]:
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]


def revise_resume_for_job(job: JobDescription, resume_text: str) -> ResumeRevisionResult:
    job_id = getattr(job, "id", "unknown")
    normalized_resume_text = _trim_resume_text_for_llm(resume_text)

    if not llm_available():
        logger.warning("resume_revision mode=fallback job_id=%s reason=missing_deepseek_api_key", job_id)
        return _build_resume_revision_fallback(job, normalized_resume_text)

    logger.info(
        "resume_revision mode=deepseek job_id=%s model=%s timeout=%s resume_chars=%s",
        job_id,
        settings.deepseek_model,
        settings.deepseek_timeout_seconds,
        len(normalized_resume_text),
    )

    try:
        llm = _with_max_tokens(build_llm(), max_tokens=1100)
        structured_llm = llm.with_structured_output(
            ResumeRevisionStructuredOutput,
            method="function_calling",
            include_raw=True,
            strict=True,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "你是一名资深求职顾问。"
                        "你的任务是基于当前简历与目标岗位的匹配情况，给出修订后的简历和匹配度评分。"
                        "匹配度评分必须针对当前简历与岗位的匹配程度，而不是针对岗位 JD 本身。"
                        "一般情况下使用中文自然表达；遇到英文书名、网站名、产品名、框架名、模型名、技术术语或行业通用专有名词时保留原文。"
                        "请保持内容真实，不得编造不存在的项目、经历或成果。"
                        "不要使用 Markdown 强调、星号列表或井号标题。"
                        "修订后的简历请控制在精炼、可直接投递的长度。"
                    ),
                ),
                (
                    "human",
                    (
                        "目标岗位：{job_title}\n"
                        "公司：{company}\n"
                        "岗位 JD：\n{jd_text}\n\n"
                        "岗位分析：\n{analysis_result}\n\n"
                        "原始简历：\n{resume_text}\n\n"
                        "请输出：\n"
                        "1. 修订后简历与岗位的匹配度评分\n"
                        "2. 对评分的简要解释\n"
                        "3. 修订后的完整简历文本"
                    ),
                ),
            ]
        )
        chain = prompt | structured_llm
        result = chain.invoke(
            {
                "job_title": job.title,
                "company": job.company,
                "jd_text": job.jd_text,
                "analysis_result": job.analysis_result or "暂无岗位分析，请基于 JD 自行判断。",
                "resume_text": normalized_resume_text,
            }
        )
    except Exception as exc:
        raise ModelInvocationError(f"DeepSeek 简历修订调用失败: {exc}") from exc

    parsed = result.get("parsed") if isinstance(result, dict) else result
    if isinstance(parsed, ResumeRevisionStructuredOutput):
        return _coerce_structured_result(parsed)

    diagnostics = _extract_parse_diagnostics(result if isinstance(result, dict) else {})
    logger.error("resume_revision structured_output_failed job_id=%s %s", job_id, diagnostics)
    raise ModelInvocationError(f"DeepSeek 简历修订结构化输出失败: {diagnostics}")


async def stream_resume_revision_for_job(job: JobDescription, resume_text: str, db: Session | None = None) -> AsyncIterator[dict]:
    job_id = getattr(job, "id", "unknown")
    normalized_resume_text = _trim_resume_text_for_llm(resume_text)
    yield {"type": "start"}

    if not llm_available():
        logger.warning("resume_revision mode=fallback job_id=%s reason=missing_deepseek_api_key", job_id)
        result = _build_resume_revision_fallback(job, normalized_resume_text)
        content = _format_streaming_output(result)
        streamed = ""
        for chunk in _chunk_text(content):
            streamed += chunk
            yield {"type": "chunk", "delta": chunk, "content": streamed}
        if db is not None:
            save_resume_revision_record(db, job, resume_text, result)
        yield {
            "type": "complete",
            "content": content,
            "data": {
                "job_id": job.id,
                "revised_resume": result.revised_resume,
                "match_score": result.match_score,
                "match_explanation": result.match_explanation,
            },
        }
        return

    logger.info(
        "resume_revision mode=deepseek_stream job_id=%s model=%s timeout=%s resume_chars=%s",
        job_id,
        settings.deepseek_model,
        settings.deepseek_timeout_seconds,
        len(normalized_resume_text),
    )

    content = ""
    previous_normalized = ""
    received_chunk = False
    try:
        messages = build_resume_revision_stream_messages(job, normalized_resume_text)
        async for chunk in stream_chat_completion(messages, max_tokens=1400):
            received_chunk = True
            content += chunk
            normalized_content = normalize_streaming_content(content)
            delta = normalized_content[len(previous_normalized) :] if normalized_content.startswith(previous_normalized) else ""
            previous_normalized = normalized_content
            yield {"type": "chunk", "delta": delta, "content": normalized_content}
        result = parse_resume_stream_output(content)
        final_content = _format_streaming_output(result)
        if db is not None:
            save_resume_revision_record(db, job, resume_text, result)
        yield {
            "type": "complete",
            "content": final_content,
            "data": {
                "job_id": job.id,
                "revised_resume": result.revised_resume,
                "match_score": result.match_score,
                "match_explanation": result.match_explanation,
            },
        }
    except Exception as exc:
        if not received_chunk:
            logger.warning("resume_revision mode=fallback job_id=%s reason=%s", job_id, exc)
            result = _build_resume_revision_fallback(job, normalized_resume_text)
            content = _format_streaming_output(result)
            streamed = ""
            for chunk in _chunk_text(content):
                streamed += chunk
                yield {"type": "chunk", "delta": chunk, "content": streamed}
            if db is not None:
                save_resume_revision_record(db, job, resume_text, result)
            yield {
                "type": "complete",
                "content": content,
                "data": {
                    "job_id": job.id,
                    "revised_resume": result.revised_resume,
                    "match_score": result.match_score,
                    "match_explanation": result.match_explanation,
                },
            }
            return
        raise ModelInvocationError(f"DeepSeek 简历修订流式输出失败: {exc}") from exc
