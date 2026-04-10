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

    # 显式忽略系统代理环境变量，避免被本机无效代理拦截到 127.0.0.1:9。
    http_client = httpx.Client(trust_env=False, timeout=30.0)
    http_async_client = httpx.AsyncClient(trust_env=False, timeout=30.0)

    return ChatDeepSeek(
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        api_key=settings.deepseek_api_key,
        temperature=0.2,
        max_retries=1,
        http_client=http_client,
        http_async_client=http_async_client,
    )


class JobAnalysisAgent:
    def invoke(self, payload: dict) -> dict:
        jd_text = payload["input"]
        keywords = ", ".join(extract_keywords(jd_text))
        focus = "、".join(detect_focus_areas(jd_text))
        summary = summarize_job(jd_text)

        llm = build_llm().bind(max_tokens=700)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "你是一个求职助手，负责对岗位 JD 做结构化分析。"
                        "请直接输出中文结果，不要寒暄，不要补充额外说明。"
                        "按以下结构返回，并尽量简洁：\n"
                        "1. 岗位核心职责\n"
                        "2. 关键技能要求\n"
                        "3. 加分项\n"
                        "4. 候选人应重点强调的经历\n"
                        "5. 简历优化建议"
                    ),
                ),
                (
                    "human",
                    (
                        "岗位 JD：\n{jd_text}\n\n"
                        "工具结果：\n"
                        "关键词：{keywords}\n"
                        "岗位重点方向：{focus}\n"
                        "岗位摘要：{summary}\n"
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
        except Exception as exc:
            raise ModelInvocationError(f"DeepSeek 岗位分析调用失败: {exc}") from exc
        return {"output": result.content}


def build_job_analysis_agent() -> JobAnalysisAgent:
    return JobAnalysisAgent()
