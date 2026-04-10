from langchain_core.tools import BaseTool

from app.tools.analyze_jd_tool import analyze_jd_tool
from app.tools.rewrite_resume_tool import rewrite_resume_tool
from app.tools.save_jd_tool import save_jd_tool


def get_job_agent_tools() -> list[BaseTool]:
    return [save_jd_tool, analyze_jd_tool, rewrite_resume_tool]
