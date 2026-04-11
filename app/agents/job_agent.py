import json

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_deepseek import ChatDeepSeek

from app.config import settings
from app.exceptions import ModelInvocationError
from app.tools.jd_tools import detect_focus_areas, extract_keywords, summarize_job


def llm_available() -> bool:
    return bool(settings.deepseek_api_key)


def build_llm() -> ChatDeepSeek:
    if not llm_available():
        raise ModelInvocationError("未配置 DEEPSEEK_API_KEY，无法调用 DeepSeek 模型。")

    timeout = settings.deepseek_timeout_seconds
    http_client = httpx.Client(trust_env=False, timeout=timeout)
    http_async_client = httpx.AsyncClient(trust_env=False, timeout=timeout)

    return ChatDeepSeek(
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        api_key=settings.deepseek_api_key,
        temperature=0.2,
        max_retries=1,
        http_client=http_client,
        http_async_client=http_async_client,
    )


def _parse_json_content(content: str) -> dict:
    text = content.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("model did not return a JSON object")
    return json.loads(text[start : end + 1])


class JobAnalysisAgent:
    def invoke(self, payload: dict) -> dict:
        jd_text = payload["input"]
        keywords = ", ".join(extract_keywords(jd_text))
        focus = "、".join(detect_focus_areas(jd_text))
        summary = summarize_job(jd_text)

        llm = build_llm().bind(max_tokens=900)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "你是岗位分析专家。"
                        "请基于岗位 JD 输出严格合法的 JSON，不要输出 JSON 之外的任何说明。"
                        "JSON 必须包含以下字段："
                        "analysis_result（字符串）"
                        "和 improvement_advice（字符串数组，至少 2 条）。"
                        "岗位分析阶段不要对 JD 本身打匹配度分数，评分应留给后续简历修订阶段。"
                    ),
                ),
                (
                    "human",
                    (
                        "岗位 JD：\n{jd_text}\n\n"
                        "辅助信息：\n"
                        "关键词：{keywords}\n"
                        "岗位重点方向：{focus}\n"
                        "岗位摘要：{summary}\n\n"
                        "请输出岗位分析摘要，以及给候选人的简历优化建议。"
                    ),
                ),
            ]
        )
        try:
            chain = prompt | llm
            result = chain.invoke(
                {
                    "jd_text": jd_text,
                    "keywords": keywords,
                    "focus": focus,
                    "summary": summary,
                }
            )
            return _parse_json_content(result.content)
        except Exception as exc:
            raise ModelInvocationError(f"DeepSeek 岗位分析调用失败: {exc}") from exc


def build_job_analysis_agent() -> JobAnalysisAgent:
    return JobAnalysisAgent()
