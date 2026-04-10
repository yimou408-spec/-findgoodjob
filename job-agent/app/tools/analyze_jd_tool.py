from langchain_core.tools import tool

from app.llm.chains.jd_analyze_chain import analyze_jd


@tool
def analyze_jd_tool(content: str) -> dict:
    """Analyze a job description with LLM."""
    return analyze_jd(content)
