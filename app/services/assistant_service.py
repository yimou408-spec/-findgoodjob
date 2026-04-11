import logging
from collections.abc import AsyncIterator

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.job_agent import build_llm, llm_available, stream_chat_completion
from app.config import settings
from app.exceptions import DatabaseError, ModelInvocationError
from app.models import AssistantMessage, AssistantThread, JobDescription
from app.schemas import (
    AssistantChatResponse,
    AssistantMessageResponse,
    AssistantThreadResponse,
    ResumeRevisionRecordResponse,
)
from app.services.resume_service import get_latest_resume_revision

logger = logging.getLogger("findgoodjob.assistant_service")

MAX_RECENT_MESSAGES = 10
MAX_SUMMARY_SOURCE_MESSAGES = 24


def _message_to_response(message: AssistantMessage) -> AssistantMessageResponse:
    created_at = message.created_at.isoformat() if message.created_at else None
    return AssistantMessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        sequence=message.sequence,
        created_at=created_at,
    )


def _resume_revision_to_response(record) -> ResumeRevisionRecordResponse | None:
    if record is None:
        return None
    created_at = record.created_at.isoformat() if record.created_at else None
    return ResumeRevisionRecordResponse(
        id=record.id,
        job_id=record.job_id,
        source_resume_text=record.source_resume_text,
        revised_resume=record.revised_resume,
        match_score=record.match_score,
        match_explanation=record.match_explanation,
        created_at=created_at,
    )


def _build_workspace_summary(job: JobDescription, latest_revision) -> str:
    parts = [
        f"当前岗位：{job.title}",
        f"目标公司：{job.company}",
        "岗位 JD：",
        job.jd_text.strip(),
        "",
        "岗位分析结果：",
        (job.analysis_result or "暂无岗位分析结果。").strip(),
        "",
        "岗位分析建议：",
        (job.analysis_improvement_advice or "暂无岗位分析建议。").strip(),
    ]

    if latest_revision is None:
        parts.extend(["", "最近一次简历修订：", "暂无简历修订结果。"])
    else:
        parts.extend(
            [
                "",
                "最近一次简历修订输入：",
                latest_revision.source_resume_text.strip(),
                "",
                "最近一次简历修订输出：",
                latest_revision.revised_resume.strip(),
                "",
                "最近一次匹配度评分：",
                str(latest_revision.match_score if latest_revision.match_score is not None else "暂无评分"),
                "",
                "最近一次评分说明：",
                (latest_revision.match_explanation or "暂无评分说明。").strip(),
            ]
        )

    return "\n".join(parts).strip()


def _build_summary_fallback(messages: list[AssistantMessage]) -> str:
    if not messages:
        return "暂无对话记忆。"

    recent_user_inputs = [message.content.strip() for message in messages if message.role == "user" and message.content.strip()]
    recent_assistant_outputs = [
        message.content.strip() for message in messages if message.role == "assistant" and message.content.strip()
    ]

    summary_parts = [
        "用户近期关注点：",
        "；".join(recent_user_inputs[-4:]) or "暂无。",
        "",
        "助手最近建议：",
        "；".join(recent_assistant_outputs[-2:]) or "暂无。",
    ]
    return "\n".join(summary_parts).strip()


def _build_messages_for_summary(workspace_summary: str, messages: list[AssistantMessage]) -> str:
    lines = ["[工作台摘要]", workspace_summary, "", "[最近对话]"]
    for message in messages[-MAX_SUMMARY_SOURCE_MESSAGES:]:
        role_label = "用户" if message.role == "user" else "助手"
        lines.append(f"{role_label}：{message.content.strip()}")
    return "\n".join(lines).strip()


def _summarize_thread_memory(workspace_summary: str, messages: list[AssistantMessage]) -> str:
    if not messages:
        return "暂无对话记忆。"

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "你是求职助手的记忆整理器。请基于工作台摘要和最近对话，用中文输出一份可供后续对话复用的简洁摘要。"
                    "只保留高价值信息：用户目标、简历弱项、偏好、已给建议、待办动作、风险点。"
                    "不要编造信息，不要输出多余寒暄。"
                ),
            ),
            ("human", "{content}"),
        ]
    )

    try:
        llm = build_llm().bind(max_tokens=500)
        result = (prompt | llm).invoke({"content": _build_messages_for_summary(workspace_summary, messages)})
        content = result.content if hasattr(result, "content") else str(result)
        normalized = content.strip()
        return normalized or _build_summary_fallback(messages)
    except Exception as exc:  # pragma: no cover - fallback path
        logger.warning("assistant_summary fallback reason=%s", exc)
        return _build_summary_fallback(messages)


def _build_assistant_messages(
    workspace_summary: str,
    summary_text: str | None,
    recent_messages: list[AssistantMessage],
    user_message: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "你是 FindGoodJob 的 AI 求职助手。请使用中文回答，基于用户当前岗位上下文、岗位分析、简历修订结果和历史对话给出建议。"
                "不要编造不存在的经历、项目、结果或面试反馈。"
                "如果信息不足，明确指出缺失信息并告诉用户下一步该补什么。"
                "回答应偏专业、可执行、适合真实求职场景。"
            ),
        },
        {"role": "system", "content": f"[岗位工作台摘要]\n{workspace_summary}"},
    ]

    if summary_text:
        messages.append({"role": "system", "content": f"[线程记忆摘要]\n{summary_text}"})

    for message in recent_messages:
        messages.append({"role": message.role, "content": message.content})

    messages.append({"role": "user", "content": user_message})
    return messages


def get_or_create_assistant_thread(db: Session, job: JobDescription) -> AssistantThread:
    try:
        thread = db.query(AssistantThread).filter(AssistantThread.job_id == job.id).first()
        if thread:
            return thread

        thread = AssistantThread(job_id=job.id, summary_text="暂无对话记忆。", workspace_summary="")
        db.add(thread)
        db.commit()
        db.refresh(thread)
        return thread
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("创建求职助手线程失败") from exc


def list_thread_messages(db: Session, thread_id: int) -> list[AssistantMessage]:
    try:
        return (
            db.query(AssistantMessage)
            .filter(AssistantMessage.thread_id == thread_id)
            .order_by(AssistantMessage.sequence.asc(), AssistantMessage.id.asc())
            .all()
        )
    except SQLAlchemyError as exc:
        raise DatabaseError("查询求职助手消息失败") from exc


def _next_sequence(db: Session, thread_id: int) -> int:
    try:
        last_message = (
            db.query(AssistantMessage)
            .filter(AssistantMessage.thread_id == thread_id)
            .order_by(AssistantMessage.sequence.desc(), AssistantMessage.id.desc())
            .first()
        )
        return (last_message.sequence if last_message else 0) + 1
    except SQLAlchemyError as exc:
        raise DatabaseError("计算求职助手消息序号失败") from exc


def save_assistant_message(db: Session, thread: AssistantThread, role: str, content: str) -> AssistantMessage:
    message = AssistantMessage(
        thread_id=thread.id,
        role=role,
        content=content.strip(),
        sequence=_next_sequence(db, thread.id),
    )
    try:
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("保存求职助手消息失败") from exc


def refresh_workspace_summary(db: Session, thread: AssistantThread, job: JobDescription) -> str:
    latest_revision = get_latest_resume_revision(db, job.id)
    summary = _build_workspace_summary(job, latest_revision)
    try:
        thread.workspace_summary = summary
        db.add(thread)
        db.commit()
        db.refresh(thread)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("更新工作台摘要失败") from exc
    return summary


def refresh_thread_summary(db: Session, thread: AssistantThread) -> str:
    messages = list_thread_messages(db, thread.id)
    summary_text = _summarize_thread_memory(thread.workspace_summary or "", messages)
    try:
        thread.summary_text = summary_text
        db.add(thread)
        db.commit()
        db.refresh(thread)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseError("更新助手记忆摘要失败") from exc
    return summary_text


def get_assistant_thread_state(db: Session, job: JobDescription) -> AssistantThreadResponse:
    thread = get_or_create_assistant_thread(db, job)
    workspace_summary = refresh_workspace_summary(db, thread, job)
    messages = list_thread_messages(db, thread.id)
    if messages and not thread.summary_text:
        refresh_thread_summary(db, thread)
        messages = list_thread_messages(db, thread.id)
    latest_revision = get_latest_resume_revision(db, job.id)
    return AssistantThreadResponse(
        thread_id=thread.id,
        job_id=job.id,
        can_chat=llm_available(),
        summary_text=thread.summary_text,
        workspace_summary=workspace_summary,
        messages=[_message_to_response(message) for message in messages],
        latest_resume_revision=_resume_revision_to_response(latest_revision),
    )


async def stream_assistant_chat(db: Session, job: JobDescription, message: str) -> AsyncIterator[dict]:
    thread = get_or_create_assistant_thread(db, job)
    workspace_summary = refresh_workspace_summary(db, thread, job)
    user_message = save_assistant_message(db, thread, "user", message)

    yield {"type": "start"}

    if not llm_available():
        raise ModelInvocationError("未配置 DEEPSEEK_API_KEY，无法使用求职助手。", error_code="assistant_llm_unavailable")

    recent_messages = list_thread_messages(db, thread.id)[-MAX_RECENT_MESSAGES:]
    prompt_messages = _build_assistant_messages(
        workspace_summary=workspace_summary,
        summary_text=thread.summary_text,
        recent_messages=recent_messages[:-1],
        user_message=user_message.content,
    )

    logger.info("assistant_chat mode=deepseek_stream job_id=%s thread_id=%s", job.id, thread.id)

    content = ""
    async for chunk in stream_chat_completion(prompt_messages, max_tokens=1200):
        content += chunk
        yield {"type": "chunk", "delta": chunk, "content": content}

    normalized_content = content.strip()
    if not normalized_content:
        raise ModelInvocationError("DeepSeek 未返回有效助手回复。", error_code="assistant_empty_response")

    assistant_message = save_assistant_message(db, thread, "assistant", normalized_content)
    summary_text = refresh_thread_summary(db, thread)

    yield {
        "type": "complete",
        "content": normalized_content,
        "data": AssistantChatResponse(
            thread_id=thread.id,
            job_id=job.id,
            message=_message_to_response(assistant_message),
            summary_text=summary_text,
            workspace_summary=thread.workspace_summary or workspace_summary,
        ).model_dump(),
    }
