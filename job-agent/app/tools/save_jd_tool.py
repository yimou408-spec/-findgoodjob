from langchain_core.tools import tool


@tool
def save_jd_tool(title: str, company: str, content: str) -> str:
    """Save JD (placeholder tool: wire with DB service in agent runtime)."""
    return f"JD received: {title} @ {company}, length={len(content)}"
