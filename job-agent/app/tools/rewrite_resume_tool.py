from langchain_core.tools import tool

from app.llm.chains.resume_rewrite_chain import rewrite_resume


@tool
def rewrite_resume_tool(jd_content: str, resume_content: str) -> dict:
    """Rewrite resume according to JD."""
    return rewrite_resume(jd_content, resume_content)
