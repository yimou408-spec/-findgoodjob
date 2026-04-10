from langchain_core.prompts import ChatPromptTemplate

from app.llm.client import get_chat_model
from app.llm.output_parsers.structured_parser import parse_json

_PROMPT = ChatPromptTemplate.from_template(
    """
你是求职助手。请分析如下岗位JD并返回JSON：
{
  "summary": "一句话总结",
  "required_skills": ["技能1", "技能2"],
  "risks": ["风险1", "风险2"]
}
JD:
{jd_content}
""".strip()
)


def analyze_jd(jd_content: str) -> dict:
    chain = _PROMPT | get_chat_model()
    resp = chain.invoke({"jd_content": jd_content})
    return parse_json(resp.content)
