import logging

from langchain_core.prompts import ChatPromptTemplate

from app.agents.job_agent import build_llm, llm_available
from app.config import settings
from app.exceptions import ModelInvocationError
from app.models import JobDescription
from app.tools.jd_tools import detect_focus_areas, extract_keywords

logger = logging.getLogger("findgoodjob.resume_service")


def _with_max_tokens(llm, max_tokens: int):
    return llm.bind(max_tokens=max_tokens) if hasattr(llm, "bind") else llm


def _build_resume_revision_fallback(job: JobDescription, resume_text: str) -> str:
    keywords = extract_keywords(job.jd_text, top_k=8)
    focus = detect_focus_areas(job.jd_text)
    focus_text = "、".join(focus)
    missing_keywords = [keyword for keyword in keywords if keyword.lower() not in resume_text.lower()][:5]

    return (
        "1. 岗位匹配度判断\n"
        f"- 候选人与目标岗位《{job.title}》存在基础匹配，但需要更突出与岗位直接相关的经验。\n\n"
        "2. 关键差距\n"
        f"- 当前简历对以下关键词体现不足：{', '.join(missing_keywords) if missing_keywords else '暂无明显缺失'}\n"
        f"- 岗位重点方向包括：{focus_text}\n\n"
        "3. 优化建议\n"
        f"- 在项目经历中补充与 {focus_text} 相关的具体实践\n"
        "- 用结果导向语言描述技能与产出\n"
        f"- 将以下关键词自然融入简历：{', '.join(keywords)}\n\n"
        "4. 修订后的简历文本\n"
        f"{resume_text}\n\n"
        "【建议重写方向】\n"
        f"应突出与 {job.title} 最相关的项目、技术栈和业务成果，并保持内容真实可验证。"
    )


def revise_resume_for_job(job: JobDescription, resume_text: str) -> str:
    job_id = getattr(job, "id", "unknown")

    if not llm_available():
        logger.warning("resume_revision mode=fallback job_id=%s reason=missing_deepseek_api_key", job_id)
        return _build_resume_revision_fallback(job, resume_text)

    logger.info("resume_revision mode=deepseek job_id=%s model=%s", job_id, settings.deepseek_model)

    llm = _with_max_tokens(build_llm(), max_tokens=1200)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "你是一名资深求职顾问。"
                    "请根据岗位 JD、岗位分析和原始简历，直接输出最终修订结果。"
                    "不要寒暄，不要解释过程，不要反问，不要要求补充信息。"
                    "输出必须使用中文，并严格按以下结构：\n"
                    "1. 岗位匹配度判断：2-3 句\n"
                    "2. 关键差距：最多 3 条\n"
                    "3. 优化建议：最多 4 条\n"
                    "4. 修订后的简历文本：输出 1 份可直接使用的精简版简历，控制在 350-500 字\n"
                    "必须保持内容真实，不得编造不存在的项目或经历。"
                ),
            ),
            (
                "human",
                (
                    "目标岗位：{job_title}\n"
                    "公司：{company}\n"
                    "岗位 JD：\n{jd_text}\n\n"
                    "岗位分析：\n{analysis_result}\n\n"
                    "原始简历：\n{resume_text}"
                ),
            ),
        ]
    )

    try:
        chain = prompt | llm
        result = chain.invoke(
            {
                "job_title": job.title,
                "company": job.company,
                "jd_text": job.jd_text,
                "analysis_result": job.analysis_result or "暂无岗位分析，请基于 JD 自行判断。",
                "resume_text": resume_text,
            }
        )
    except Exception as exc:
        raise ModelInvocationError(f"DeepSeek 简历修订调用失败: {exc}") from exc

    return result.content
