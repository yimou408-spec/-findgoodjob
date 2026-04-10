import re
from collections import Counter

from langchain.tools import tool

STOP_WORDS = {
    "负责",
    "熟悉",
    "相关",
    "以上",
    "优先",
    "岗位",
    "任职要求",
    "岗位职责",
    "进行",
    "工作",
    "能力",
    "经验",
}


def _tokenize(text: str) -> list[str]:
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", " ", text)
    tokens = [token.strip().lower() for token in normalized.split() if len(token.strip()) > 1]
    return [token for token in tokens if token not in STOP_WORDS]


def extract_keywords(jd_text: str, top_k: int = 12) -> list[str]:
    tokens = _tokenize(jd_text)
    return [word for word, _ in Counter(tokens).most_common(top_k)]


def detect_focus_areas(jd_text: str) -> list[str]:
    lowered = jd_text.lower()
    focus = []
    if any(keyword in lowered for keyword in ["langchain", "langgraph", "agent", "workflow"]):
        focus.append("Agent 工作流编排")
    if any(keyword in lowered for keyword in ["rag", "retrieval", "向量", "embedding"]):
        focus.append("RAG / 检索增强")
    if any(keyword in lowered for keyword in ["python", "fastapi", "java", "golang"]):
        focus.append("工程开发能力")
    if any(keyword in lowered for keyword in ["算法", "nlp", "模型", "llm", "deepseek"]):
        focus.append("大模型 / 算法理解")
    if any(keyword in lowered for keyword in ["业务", "产品", "需求", "沟通"]):
        focus.append("业务协同能力")
    if not focus:
        focus.append("通用软件工程与岗位理解能力")
    return focus


def summarize_job(jd_text: str, max_chars: int = 300) -> str:
    cleaned = re.sub(r"\s+", " ", jd_text).strip()
    return cleaned[:max_chars]


@tool
def extract_keywords_tool(jd_text: str) -> str:
    """提取岗位 JD 中最重要的关键词，用于帮助 Agent 识别技能要求与业务重点。"""
    return "关键词：" + ", ".join(extract_keywords(jd_text))


@tool
def skill_gap_focus_tool(jd_text: str) -> str:
    """判断 JD 更偏向工程、算法、业务理解还是 Agent/RAG 能力。"""
    return "岗位重点方向：" + "、".join(detect_focus_areas(jd_text))


@tool
def rewrite_job_summary_tool(jd_text: str) -> str:
    """将 JD 压缩为后续简历修订更容易使用的岗位摘要。"""
    return f"岗位摘要：{summarize_job(jd_text)}"
