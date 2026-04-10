from langchain_core.prompts import ChatPromptTemplate

from app.llm.client import get_chat_model
from app.llm.output_parsers.structured_parser import parse_json

_PROMPT = ChatPromptTemplate.from_template(
    """
你是资深求职顾问。根据JD改写简历，返回JSON：
{
  "revised_content": "改写后的简历全文",
  "rationale": "改写理由"
}
JD:
{jd_content}
原简历:
{resume_content}
""".strip()
)


def rewrite_resume(jd_content: str, resume_content: str) -> dict:
    chain = _PROMPT | get_chat_model()
    resp = chain.invoke({"jd_content": jd_content, "resume_content": resume_content})
    return parse_json(resp.content)
